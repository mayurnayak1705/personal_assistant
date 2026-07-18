"""Persistent MCP client used by the planner and reminder notification API."""

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


class ReminderMCPClient:
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
                args=["-m", "mcp_servers.reminder.server"],
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
                self._start_error = f"Reminder MCP is unavailable: {exc}"
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
        debug("TOOL", "call", integration="reminder", tool=name, parameters=arguments)
        await self.start()
        assert self._session is not None
        async with self._call_lock:
            result = await self._session.call_tool(name, arguments)
        text = "\n".join(
            str(item.text)
            for item in result.content
            if getattr(item, "type", None) == "text"
        )
        is_error = bool(getattr(result, "isError", False))
        debug("TOOL", "result", integration="reminder", tool=name, is_error=is_error, output_chars=len(text))
        return text, is_error

    async def due_reminders(self, user_id: str, limit: int = 50) -> dict[str, Any]:
        text, is_error = await self._call_tool(
            "list_due_reminders",
            {"user_id": user_id, "limit": limit},
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def reminders_between(
        self,
        *,
        user_id: str,
        time_min: str,
        time_max: str,
        limit: int = 200,
    ) -> dict[str, Any]:
        text, is_error = await self._call_tool(
            "list_reminders",
            {
                "user_id": user_id,
                "time_min": time_min,
                "time_max": time_max,
                "limit": limit,
            },
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def acknowledge(self, reminder_id: str, user_id: str) -> dict[str, Any]:
        text, is_error = await self._call_tool(
            "acknowledge_reminder",
            {"reminder_id": reminder_id, "user_id": user_id},
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    @staticmethod
    def _conversation_input(messages: Iterable[Any]) -> list[dict[str, str]]:
        output: list[dict[str, str]] = []
        for message in messages:
            message_type = getattr(message, "type", "")
            if message_type in {"human", "ai"}:
                output.append(
                    {
                        "role": "user" if message_type == "human" else "assistant",
                        "content": str(getattr(message, "content", "")),
                    }
                )
        return output

    async def execute(
        self,
        *,
        user_id: str,
        user_input: str,
        system_prompt: str,
        messages: Iterable[Any] = (),
    ) -> ToolExecutionResult:
        await self.start()
        assert self._session is not None
        async with self._call_lock:
            listed = await self._session.list_tools()
        tools = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            }
            for tool in listed.tools
        ]

        now = datetime.now(self.timezone)
        date_context = (
            f"Current datetime: {now.isoformat(timespec='seconds')}\n"
            f"Timezone: {self.timezone.key}\n"
            "Resolve relative times such as 'after 30 minutes' from this exact datetime. "
            "Pass reminder_time as an ISO-8601 datetime with timezone offset."
        )
        conversation = self._conversation_input(messages)
        if not conversation or conversation[-1].get("content") != user_input:
            conversation.append({"role": "user", "content": user_input})

        response = await self._openai.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": date_context + "\n\n" + system_prompt},
                *conversation,
            ],
            tools=tools,
        )
        events: list[dict[str, Any]] = []

        for _ in range(8):
            tool_calls = [item for item in response.output if item.type == "function_call"]
            if not tool_calls:
                return ToolExecutionResult(
                    text=response.output_text or "The reminder request did not produce a response.",
                    events=events,
                )

            outputs: list[dict[str, str]] = []
            for tool_call in tool_calls:
                arguments = json.loads(tool_call.arguments or "{}")
                if tool_call.name in {
                    "create_reminder",
                    "list_due_reminders",
                    "acknowledge_reminder",
                }:
                    arguments["user_id"] = user_id
                result, is_error = await self._call_tool(tool_call.name, arguments)
                events.append(
                    build_tool_event(
                        integration="reminders",
                        tool_name=tool_call.name,
                        arguments=arguments,
                        output=result,
                        is_error=is_error,
                    )
                )
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": result,
                    }
                )
            response = await self._openai.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=outputs,
                tools=tools,
            )

        return ToolExecutionResult(
            text="I could not complete the reminder request after several tool steps.",
            events=events,
        )


reminder_client = ReminderMCPClient()
