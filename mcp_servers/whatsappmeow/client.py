"""Persistent MCP client for the local whatsmeow server.

The server must stay connected for inbound WhatsApp events to be logged. This
client therefore owns one stdio session for the FastAPI application's lifetime
and serializes MCP calls over it.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from openai import AsyncOpenAI
from working_context import ToolExecutionResult, build_tool_event

load_dotenv()


class WhatsAppMCPClient:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.server_dir = Path(__file__).resolve().parent
        self._openai = AsyncOpenAI()
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._start_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()
        self._last_start_attempt = 0.0
        self._start_error: str | None = None
        self._state_path = self.server_dir / "integration-state.json"
        self._enabled = self._load_enabled_state()
        # Refreshed from list_contacts. The WhatsApp contact store remains the
        # persistent source of truth; this map gives the planner fast, explicit
        # name -> candidate-number visibility for the current process.
        self.contact_map: dict[str, list[dict[str, str]]] = {}
        # A clarification is a two-turn operation. Keep its exact message and
        # candidates keyed by chat so a short answer such as "Pp", a number,
        # or "option 2" cannot be reinterpreted by the model.
        self.pending_sends: dict[str, dict[str, Any]] = {}

    @property
    def connected(self) -> bool:
        return self._session is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "error": self._start_error,
        }

    def _load_enabled_state(self) -> bool:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            return bool(payload.get("enabled", True))
        except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
            return True

    def _persist_enabled_state(self) -> None:
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"enabled": self._enabled}, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self._state_path)

    async def start_if_enabled(self) -> None:
        if self.enabled:
            await self.start()

    async def set_enabled(self, enabled: bool) -> dict[str, Any]:
        enabled = bool(enabled)
        if enabled == self._enabled:
            if enabled and not self.connected:
                await self.start()
            return self.status

        self._enabled = enabled
        self._persist_enabled_state()
        self.pending_sends.clear()

        if enabled:
            await self.start()
        else:
            # Wait for any in-flight send/poll to finish before disconnecting.
            async with self._call_lock:
                await self.stop()
            self.contact_map.clear()
            self._start_error = None
        return self.status

    async def start(self) -> None:
        if not self.enabled:
            raise RuntimeError("WhatsApp integration is turned off.")
        if self._session is not None:
            return

        async with self._start_lock:
            if self._session is not None:
                return
            # Avoid spawning a Go process on every two-second UI poll when the
            # account is unpaired or temporarily offline.
            now = time.monotonic()
            if self._start_error and now - self._last_start_attempt < 10:
                raise RuntimeError(self._start_error)
            self._last_start_attempt = now

            env = os.environ.copy()
            env.setdefault(
                "WHATSMEOW_SESSION_DB",
                str(self.server_dir / "whatsmeow-session.db"),
            )
            env.setdefault(
                "WHATSMEOW_LOG_DB",
                str(self.server_dir / "whatsmeow-message-log.db"),
            )
            params = StdioServerParameters(
                command="go",
                # Do not use `go run .`: main.go is a separate QR-pairing demo.
                args=["run", "mcp_server.go"],
                cwd=self.server_dir,
                env=env,
            )

            stack = AsyncExitStack()
            try:
                read_stream, write_stream = await stack.enter_async_context(
                    stdio_client(params)
                )
                session = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
            except Exception as exc:
                await stack.aclose()
                self._start_error = f"WhatsApp MCP is unavailable: {exc}"
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
        if not self.enabled:
            raise RuntimeError("WhatsApp integration is turned off. Turn it on before sending or receiving messages.")
        await self.start()
        assert self._session is not None
        async with self._call_lock:
            result = await self._session.call_tool(name, arguments)
        text = "\n".join(
            str(item.text)
            for item in result.content
            if getattr(item, "type", None) == "text"
        )
        return text, bool(getattr(result, "isError", False))

    async def list_contacts(self, query: str = "") -> dict[str, Any]:
        text, is_error = await self._call_tool("list_contacts", {"query": query})
        if is_error:
            raise RuntimeError(text)
        payload = json.loads(text)
        for contact in payload.get("contacts", []):
            key = str(contact.get("name", "")).strip().casefold()
            if key:
                candidates = self.contact_map.setdefault(key, [])
                if contact not in candidates:
                    candidates.append(contact)
        return payload

    async def poll_messages(
        self,
        after_id: int | None,
        limit: int = 50,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {"limit": limit}
        if after_id is not None:
            arguments["after_id"] = after_id
        text, is_error = await self._call_tool("poll_messages", arguments)
        if is_error:
            raise RuntimeError(text)
        return json.loads(text)

    @staticmethod
    def _conversation_input(messages: Iterable[Any]) -> list[dict[str, str]]:
        conversation: list[dict[str, str]] = []
        for message in messages:
            message_type = getattr(message, "type", "")
            if message_type not in {"human", "ai"}:
                continue
            conversation.append(
                {
                    "role": "user" if message_type == "human" else "assistant",
                    "content": str(getattr(message, "content", "")),
                }
            )
        return conversation

    @staticmethod
    def _contact_question(contacts: list[dict[str, Any]]) -> str:
        options = "\n".join(
            f"{index}. {contact.get('name', 'Unknown')} ({contact.get('phone_number', 'unknown number')})"
            for index, contact in enumerate(contacts, start=1)
        )
        return f"I found multiple matching WhatsApp contacts. Which one do you mean?\n\n{options}"

    @staticmethod
    def _exact_contacts(
        contacts: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        normalized = query.strip().casefold()
        digits = re.sub(r"\D", "", query)
        exact: list[dict[str, Any]] = []
        seen_numbers: set[str] = set()
        for contact in contacts:
            number = str(contact.get("phone_number", ""))
            names = [contact.get("name", ""), *contact.get("aliases", [])]
            name_matches = any(
                str(name).strip().casefold() == normalized for name in names if name
            )
            number_matches = bool(digits) and number == digits
            if (name_matches or number_matches) and number not in seen_numbers:
                exact.append(contact)
                seen_numbers.add(number)
        return exact

    @staticmethod
    def _pending_selection(
        answer: str,
        contacts: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        exact = WhatsAppMCPClient._exact_contacts(contacts, answer)
        if len(exact) == 1:
            return exact[0]

        normalized = answer.strip().casefold()
        ordinal_words = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
            "sixth": 6,
            "seventh": 7,
            "eighth": 8,
            "ninth": 9,
            "tenth": 10,
        }
        selected_index: int | None = None
        for word, index in ordinal_words.items():
            if re.search(rf"\b{word}\b", normalized):
                selected_index = index
                break
        if selected_index is None:
            match = re.search(r"(?:option\s*)?(\d+)(?:st|nd|rd|th)?(?:\s*(?:one|option))?", normalized)
            if match:
                selected_index = int(match.group(1))
        if selected_index is not None and 1 <= selected_index <= len(contacts):
            return contacts[selected_index - 1]
        return None

    @staticmethod
    def _is_send_request(user_input: str) -> bool:
        normalized = user_input.casefold()
        return bool(
            re.search(r"\bsend\b", normalized)
            or re.search(r"\b(?:text|message)\s+(?:to\s+)?\S+", normalized)
        )

    async def _continue_pending_send(
        self,
        conversation_id: str,
        user_input: str,
        events: list[dict[str, Any]],
    ) -> str | None:
        pending = self.pending_sends.get(conversation_id)
        if not pending:
            return None

        if user_input.strip().casefold() in {"cancel", "cancel it", "never mind", "nevermind"}:
            self.pending_sends.pop(conversation_id, None)
            return "Okay, I cancelled the WhatsApp message."

        contacts = pending["contacts"]
        selected = self._pending_selection(user_input, contacts)
        if selected is None:
            return "I couldn't match that selection.\n\n" + self._contact_question(contacts)

        output, is_error = await self._call_tool(
            "send_message",
            {
                "contact": selected["phone_number"],
                "message": pending["message"],
            },
        )
        events.append(
            build_tool_event(
                integration="whatsapp",
                tool_name="send_message",
                arguments={
                    "contact": selected["phone_number"],
                    "message": pending["message"],
                },
                output=output,
                is_error=is_error,
            )
        )
        if not is_error:
            self.pending_sends.pop(conversation_id, None)
        return output

    async def execute(
        self,
        conversation_id: str,
        user_input: str,
        system_prompt: str,
        messages: Iterable[Any] = (),
    ) -> ToolExecutionResult:
        """Let the planner use MCP tools, with contact safety enforced in code."""
        await self.start()
        assert self._session is not None

        events: list[dict[str, Any]] = []
        pending_result = await self._continue_pending_send(conversation_id, user_input, events)
        if pending_result is not None:
            return ToolExecutionResult(text=pending_result, events=events)

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
            # poll_messages is for the UI bridge, not agent planning.
            if tool.name != "poll_messages"
        ]

        conversation = self._conversation_input(messages)
        if not conversation or conversation[-1].get("content") != user_input:
            conversation.append({"role": "user", "content": user_input})
        response = await self._openai.responses.create(
            model=self.model,
            input=[{"role": "system", "content": system_prompt}, *conversation],
            tools=tools,
        )

        send_requested = self._is_send_request(user_input)
        send_called = False
        send_nudged = False

        for _ in range(8):
            tool_calls = [
                item for item in response.output if item.type == "function_call"
            ]
            if not tool_calls:
                if send_requested and not send_called and not send_nudged:
                    # Some models stop after contact lookup to ask for an
                    # unnecessary confirmation. The original send instruction
                    # is already authorization; nudge once while the safety
                    # resolver below still guards ambiguous destinations.
                    response = await self._openai.responses.create(
                        model=self.model,
                        previous_response_id=response.id,
                        input=[
                            {
                                "role": "developer",
                                "content": (
                                    "The user already explicitly authorized this send. "
                                    "Do not ask for confirmation. Call send_message now "
                                    "using the exact requested text and recipient."
                                ),
                            }
                        ],
                        tools=tools,
                    )
                    send_nudged = True
                    continue
                return ToolExecutionResult(
                    text=response.output_text or "The WhatsApp request did not produce a response.",
                    events=events,
                )

            outputs: list[dict[str, str]] = []
            for tool_call in tool_calls:
                arguments = json.loads(tool_call.arguments or "{}")

                if tool_call.name == "send_message":
                    send_called = True
                    recipient = str(arguments.get("contact", "")).strip()
                    resolution = await self.list_contacts(recipient)
                    contacts = resolution.get("contacts", [])
                    exact_contacts = self._exact_contacts(contacts, recipient)
                    if exact_contacts:
                        # Exact saved-name/number matches always outrank partial
                        # suggestions such as Pp -> Appa or Shivappa.
                        contacts = exact_contacts
                    if len(contacts) > 1:
                        self.pending_sends[conversation_id] = {
                            "message": str(arguments.get("message", "")),
                            "contacts": contacts,
                        }
                        return ToolExecutionResult(text=self._contact_question(contacts), events=events)
                    if not contacts:
                        return ToolExecutionResult(
                            text=f'I could not find a WhatsApp contact matching "{recipient}". Who should I message?',
                            events=events,
                        )
                    # Address by the exact number returned by the contact store,
                    # never by an ambiguous display name.
                    arguments["contact"] = contacts[0]["phone_number"]

                output, is_error = await self._call_tool(tool_call.name, arguments)
                events.append(
                    build_tool_event(
                        integration="whatsapp",
                        tool_name=tool_call.name,
                        arguments=arguments,
                        output=output,
                        is_error=is_error,
                    )
                )
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": output,
                    }
                )

            response = await self._openai.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=outputs,
                tools=tools,
            )

        return ToolExecutionResult(
            text="I could not complete the WhatsApp request after several tool steps.",
            events=events,
        )


whatsapp_client = WhatsAppMCPClient()
