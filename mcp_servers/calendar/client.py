"""Persistent Calendar MCP client used by the planner and API."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from working_context import ToolExecutionResult, build_tool_event
from debug_log import debug
from model_provider import configured_model, create_async_responses_client


load_dotenv()


def _friendly_calendar_error(value: str) -> str:
    text = str(value)
    if "accessNotConfigured" in text or "calendar-json.googleapis.com" in text and "disabled" in text:
        return (
            "The Google Calendar API is disabled for the configured Cloud project. "
            "Enable the Google Calendar API in Google Cloud Console, wait a minute for propagation, and retry."
        )
    if "insufficientPermissions" in text or "insufficient authentication scopes" in text.casefold():
        return "Google Calendar authorization is missing the calendar.events permission. Reconnect Calendar OAuth."
    return text


class CalendarMCPClient:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or configured_model("gpt-4o-mini")
        self.project_root = Path(__file__).resolve().parents[2]
        self.timezone = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
        self._openai = create_async_responses_client()
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._start_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()
        self._start_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._session is not None

    @property
    def status(self) -> dict[str, Any]:
        return {"connected": self.connected, "error": self._start_error}

    async def start(self) -> None:
        if self._session is not None:
            return
        async with self._start_lock:
            if self._session is not None:
                return
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_servers.calendar.server"],
                cwd=self.project_root,
                env=os.environ.copy(),
            )
            stack = AsyncExitStack()
            try:
                read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await session.initialize()
            except Exception as exc:
                await stack.aclose()
                self._start_error = f"Calendar MCP is unavailable: {exc}"
                raise RuntimeError(self._start_error) from exc
            self._stack = stack
            self._session = session
            self._start_error = None

    async def stop(self) -> None:
        async with self._start_lock:
            stack, self._stack = self._stack, None
            self._session = None
            if stack is not None:
                await stack.aclose()

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        debug("TOOL", "call", integration="calendar", tool=name, parameters=arguments)
        await self.start()
        assert self._session is not None
        async with self._call_lock:
            result = await self._session.call_tool(name, arguments)
        output = "\n".join(
            str(item.text) for item in result.content if getattr(item, "type", None) == "text"
        )
        is_error = bool(getattr(result, "isError", False))
        debug("TOOL", "result", integration="calendar", tool=name, is_error=is_error, output_chars=len(output))
        return output, is_error

    async def connection_status(self) -> dict[str, Any]:
        text, is_error = await self._call_tool("calendar_status", {})
        if is_error:
            return {"authenticated": False, "calendar_id": None, "error": _friendly_calendar_error(text)}
        status = json.loads(text)
        if status.get("error"):
            status["error"] = _friendly_calendar_error(status["error"])
        return status

    async def upcoming_events(self, limit: int = 20) -> dict[str, Any]:
        text, is_error = await self._call_tool("list_calendar_events", {"limit": limit})
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    @staticmethod
    def _conversation_input(messages: Iterable[Any]) -> list[dict[str, str]]:
        output = []
        for message in messages:
            message_type = getattr(message, "type", "")
            if message_type in {"human", "ai"}:
                output.append({
                    "role": "user" if message_type == "human" else "assistant",
                    "content": str(getattr(message, "content", "")),
                })
        return output

    async def execute(
        self,
        *,
        user_input: str,
        system_prompt: str,
        messages: Iterable[Any] = (),
        recent_events: Iterable[dict[str, Any]] = (),
    ) -> ToolExecutionResult:
        await self.start()
        assert self._session is not None
        status = await self.connection_status()
        if not status.get("authenticated"):
            return ToolExecutionResult(
                text=f"Google Calendar is not ready: {status.get('error') or 'OAuth setup is required.'}",
                events=[],
            )
        async with self._call_lock:
            listed = await self._session.list_tools()
        tools = [
            {"type": "function", "name": tool.name, "description": tool.description, "parameters": tool.inputSchema}
            for tool in listed.tools
        ]
        now = datetime.now(self.timezone)
        date_context = (
            f"Current datetime: {now.isoformat(timespec='seconds')}\n"
            f"Timezone: {self.timezone.key}\n"
            "Resolve relative meeting times from this exact datetime. Pass start_time as ISO-8601 "
            "with an offset and timezone as an IANA timezone name."
        )
        conversation = self._conversation_input(messages)
        if not conversation or conversation[-1].get("content") != user_input:
            conversation.append({"role": "user", "content": user_input})
        response = await self._openai.responses.create(
            model=self.model,
            input=[{"role": "system", "content": date_context + "\n\n" + system_prompt}, *conversation],
            tools=tools,
        )
        events: list[dict[str, Any]] = []
        for _ in range(8):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return ToolExecutionResult(
                    text=response.output_text or "The Calendar request did not produce a response.",
                    events=events,
                )
            outputs = []
            for call in calls:
                arguments = json.loads(call.arguments or "{}")
                if call.name == "create_calendar_meeting" and self._already_created(arguments, recent_events):
                    return ToolExecutionResult(
                        text="An identical meeting was already scheduled in this conversation, so I did not send another invitation.",
                        events=events,
                    )
                result, is_error = await self._call_tool(call.name, arguments)
                events.append(build_tool_event(
                    integration="calendar",
                    tool_name=call.name,
                    arguments=arguments,
                    output=result,
                    is_error=is_error,
                ))
                if is_error:
                    return ToolExecutionResult(
                        text=f"Google Calendar could not complete the request: {_friendly_calendar_error(result)}",
                        events=events,
                    )
                outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": result})
            response = await self._openai.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=outputs,
                tools=tools,
            )
        return ToolExecutionResult(
            text="I could not complete the Calendar request after several tool steps.",
            events=events,
        )

    @staticmethod
    def _already_created(arguments: dict[str, Any], events: Iterable[dict[str, Any]]) -> bool:
        """Match a meeting against successful creates in the current context."""
        def normalized(value: Any) -> str:
            return " ".join(str(value or "").casefold().split())

        title = normalized(arguments.get("title"))
        start_time = normalized(arguments.get("start_time"))
        attendees = sorted(normalized(value) for value in arguments.get("attendees", []) if value)
        if not title or not start_time or not attendees:
            return False
        for event in events:
            if not (
                event.get("success")
                and event.get("integration") == "calendar"
                and event.get("tool_name") == "create_calendar_meeting"
            ):
                continue
            previous = event.get("arguments") or {}
            if (
                normalized(previous.get("title")) == title
                and normalized(previous.get("start_time")) == start_time
                and sorted(normalized(value) for value in previous.get("attendees", []) if value) == attendees
            ):
                return True
        return False


calendar_client = CalendarMCPClient()
