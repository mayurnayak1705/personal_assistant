"""Persistent Tasks MCP client for planner and notification APIs."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from openai import AsyncOpenAI
from working_context import ToolExecutionResult, build_tool_event
from debug_log import debug

load_dotenv()


class TasksMCPClient:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.project_root = Path(__file__).resolve().parents[2]
        self.timezone = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
        self._openai = AsyncOpenAI()
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
                args=["-m", "mcp_servers.tasks.server"],
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
                self._start_error = f"Tasks MCP is unavailable: {exc}"
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
        debug("TOOL", "call", integration="tasks", tool=name, parameters=arguments)
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
        debug("TOOL", "result", integration="tasks", tool=name, is_error=is_error, output_chars=len(text))
        return text, is_error

    async def notification_tasks(self, user_id: str, limit: int = 50) -> dict[str, Any]:
        text, is_error = await self._call_tool(
            "list_tasks",
            {"user_id": user_id, "view": "due", "limit": limit},
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def list_tasks(
        self,
        *,
        user_id: str,
        view: str = "all",
        limit: int = 200,
    ) -> dict[str, Any]:
        """Return tasks for the dedicated task-management panel."""
        text, is_error = await self._call_tool(
            "list_tasks",
            {"user_id": user_id, "view": view, "limit": limit},
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def complete(self, task_id: str, user_id: str) -> dict[str, Any]:
        text, is_error = await self._call_tool(
            "complete_task",
            {"task_id": task_id, "user_id": user_id},
        )
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    async def postpone_until_tomorrow(self, task_id: str, user_id: str) -> dict[str, Any]:
        tomorrow = datetime.now(self.timezone) + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        text, is_error = await self._call_tool(
            "update_task",
            {"task_id": task_id, "user_id": user_id, "due_at": tomorrow.isoformat()},
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
            "Resolve relative task due dates from this datetime and pass due_at as ISO-8601."
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
                return ToolExecutionResult(
                    text=response.output_text or "The task request did not produce a response.",
                    events=events,
                )
            outputs = []
            for call in calls:
                arguments = json.loads(call.arguments or "{}")
                arguments["user_id"] = user_id
                result, is_error = await self._call_tool(call.name, arguments)
                events.append(
                    build_tool_event(
                        integration="tasks",
                        tool_name=call.name,
                        arguments=arguments,
                        output=result,
                        is_error=is_error,
                    )
                )
                outputs.append(
                    {"type": "function_call_output", "call_id": call.call_id, "output": result}
                )
            response = await self._openai.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=outputs,
                tools=tools,
            )
        return ToolExecutionResult(
            text="I could not complete the task request after several tool steps.",
            events=events,
        )


tasks_client = TasksMCPClient()
