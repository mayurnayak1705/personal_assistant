"""Gmail MCP client used by the planner, API, and scheduled dispatcher."""

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

from app.memory.working_context import ToolExecutionResult, build_tool_event
from app.core.debug import debug
from app.core.models import configured_model, create_async_responses_client


load_dotenv()
USER_SCOPED_TOOLS = {"schedule_email", "list_scheduled_emails", "cancel_scheduled_email"}
INTERNAL_TOOLS = {"dispatch_due_scheduled_emails"}


class GmailMCPClient:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or configured_model("gpt-4o-mini")
        self.project_root = Path(__file__).resolve().parents[2]
        self.timezone = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
        self._openai = create_async_responses_client()
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._start_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()
        self._scheduler_task: asyncio.Task | None = None
        self._scheduler_stop: asyncio.Event | None = None
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
                args=["-m", "mcp_servers.gmail.server"],
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
                self._start_error = f"Gmail MCP is unavailable: {exc}"
                raise RuntimeError(self._start_error) from exc
            self._stack = stack
            self._session = session
            self._start_error = None
            self._scheduler_stop = asyncio.Event()
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        async with self._start_lock:
            task, self._scheduler_task = self._scheduler_task, None
            stop_event, self._scheduler_stop = self._scheduler_stop, None
            if stop_event:
                stop_event.set()
            if task:
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=10)
                except asyncio.TimeoutError:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            stack, self._stack = self._stack, None
            self._session = None
            if stack:
                await stack.aclose()

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        debug("TOOL", "call", integration="gmail", tool=name, parameters=arguments)
        await self.start()
        assert self._session is not None
        async with self._call_lock:
            result = await self._session.call_tool(name, arguments)
        text = "\n".join(str(item.text) for item in result.content if getattr(item, "type", None) == "text")
        is_error = bool(getattr(result, "isError", False))
        debug("TOOL", "result", integration="gmail", tool=name, is_error=is_error, output_chars=len(text))
        return text, is_error

    async def _scheduler_loop(self) -> None:
        stop_event = self._scheduler_stop
        if stop_event is None:
            return
        while not stop_event.is_set():
            try:
                await self._call_tool("dispatch_due_scheduled_emails", {"limit": 10})
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                pass

    async def connection_status(self) -> dict[str, Any]:
        text, is_error = await self._call_tool("gmail_status", {})
        if is_error:
            return {"authenticated": False, "email": None, "error": text}
        return json.loads(text)

    async def unread_emails(self, limit: int = 20) -> dict[str, Any]:
        text, is_error = await self._call_tool("list_unread_emails", {"limit": limit})
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def read_email(self, message_id: str) -> dict[str, Any]:
        text, is_error = await self._call_tool("read_email", {"message_id": message_id})
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def scheduled_emails(self, user_id: str, limit: int = 20) -> dict[str, Any]:
        text, is_error = await self._call_tool(
            "list_scheduled_emails", {"user_id": user_id, "status": "scheduled", "limit": limit}
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def mark_read(self, message_id: str) -> dict[str, Any]:
        text, is_error = await self._call_tool("mark_email_read", {"message_id": message_id})
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def archive(self, message_id: str) -> dict[str, Any]:
        text, is_error = await self._call_tool("archive_email", {"message_id": message_id})
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def cancel_scheduled(self, schedule_id: str, user_id: str) -> dict[str, Any]:
        text, is_error = await self._call_tool(
            "cancel_scheduled_email", {"schedule_id": schedule_id, "user_id": user_id}
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    @staticmethod
    def _conversation_input(messages: Iterable[Any]) -> list[dict[str, str]]:
        output = []
        for message in messages:
            message_type = getattr(message, "type", "")
            if message_type in {"human", "ai"}:
                output.append({"role": "user" if message_type == "human" else "assistant", "content": str(getattr(message, "content", ""))})
        return output

    async def execute(self, *, user_id: str, user_input: str, system_prompt: str, messages: Iterable[Any] = ()) -> ToolExecutionResult:
        await self.start()
        assert self._session is not None
        async with self._call_lock:
            listed = await self._session.list_tools()
        tools = [
            {"type": "function", "name": tool.name, "description": tool.description, "parameters": tool.inputSchema}
            for tool in listed.tools if tool.name not in INTERNAL_TOOLS
        ]
        now = datetime.now(self.timezone)
        date_context = (
            f"Current datetime: {now.isoformat(timespec='seconds')}\nTimezone: {self.timezone.key}\n"
            "Resolve relative send times from this datetime and pass send_at as ISO-8601 with timezone."
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
        for _ in range(10):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return ToolExecutionResult(text=response.output_text or "The Gmail request did not produce a response.", events=events)
            outputs = []
            for call in calls:
                arguments = json.loads(call.arguments or "{}")
                if call.name in USER_SCOPED_TOOLS:
                    arguments["user_id"] = user_id
                result, is_error = await self._call_tool(call.name, arguments)
                events.append(build_tool_event(integration="gmail", tool_name=call.name, arguments=arguments, output=result, is_error=is_error))
                outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": result})
            response = await self._openai.responses.create(
                model=self.model, previous_response_id=response.id, input=outputs, tools=tools
            )
        return ToolExecutionResult(text="I could not complete the Gmail request after several tool steps.", events=events)


gmail_client = GmailMCPClient()
