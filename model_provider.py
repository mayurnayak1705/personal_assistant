"""Shared OpenAI/Anthropic model selection and Responses compatibility."""

from __future__ import annotations

import json
import os
import uuid
from collections import OrderedDict
from types import SimpleNamespace
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _configured_key(name: str) -> bool:
    value = os.getenv(name, "").strip()
    return bool(value and not value.casefold().startswith("replace_"))


def model_provider() -> str:
    requested = os.getenv("LLM_PROVIDER", "auto").strip().casefold()
    if requested not in {"auto", "openai", "anthropic"}:
        raise ValueError("LLM_PROVIDER must be auto, openai, or anthropic.")
    if requested == "openai":
        if not _configured_key("OPENAI_API_KEY"):
            raise RuntimeError("LLM_PROVIDER is openai but OPENAI_API_KEY is not configured.")
        return "openai"
    if requested == "anthropic":
        if not _configured_key("ANTHROPIC_API_KEY"):
            raise RuntimeError("LLM_PROVIDER is anthropic but ANTHROPIC_API_KEY is not configured.")
        return "anthropic"
    if _configured_key("OPENAI_API_KEY"):
        return "openai"
    if _configured_key("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError("Configure either OPENAI_API_KEY or ANTHROPIC_API_KEY.")


def configured_model(default_openai: str = "gpt-4o-mini") -> str:
    if model_provider() == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    return os.getenv("OPENAI_MODEL", default_openai)


def create_chat_model(*, default_openai: str = "gpt-4o-mini", temperature: float = 0):
    provider = model_provider()
    model = configured_model(default_openai)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, temperature=temperature)


def _anthropic_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    output = []
    for tool in tools or []:
        function = tool.get("function", tool)
        output.append(
            {
                "name": function["name"],
                "description": function.get("description") or "",
                "input_schema": function.get("parameters") or function.get("input_schema") or {"type": "object"},
            }
        )
    return output


def _initial_state(input_messages: Any) -> dict[str, Any]:
    system_parts: list[str] = []
    messages: list[dict[str, Any]] = []
    for message in input_messages if isinstance(input_messages, list) else [input_messages]:
        if not isinstance(message, dict):
            messages.append({"role": "user", "content": str(message)})
            continue
        role = message.get("role", "user")
        content = message.get("content", "")
        if role in {"system", "developer"}:
            system_parts.append(str(content))
        else:
            messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})
    return {"system": "\n\n".join(system_parts), "messages": messages}


def _append_continuation(state: dict[str, Any], continuation: Any) -> None:
    tool_results: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for item in continuation if isinstance(continuation, list) else [continuation]:
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": item["call_id"],
                    "content": str(item.get("output", "")),
                }
            )
        elif isinstance(item, dict):
            text_parts.append(str(item.get("content", "")))
        else:
            text_parts.append(str(item))
    if tool_results:
        state["messages"].append({"role": "user", "content": tool_results})
    if any(text_parts):
        state["messages"].append({"role": "user", "content": "\n".join(text_parts)})


def _compat_response(response: Any) -> Any:
    output = []
    text_parts = []
    anthropic_content = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
            output.append(SimpleNamespace(type="message", text=block.text))
            anthropic_content.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            output.append(
                SimpleNamespace(
                    type="function_call",
                    name=block.name,
                    arguments=json.dumps(block.input),
                    call_id=block.id,
                )
            )
            anthropic_content.append(
                {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
            )
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        output=output,
        output_text="\n".join(text_parts).strip(),
        _anthropic_content=anthropic_content,
    )


class _AnthropicResponsesBase:
    def __init__(self) -> None:
        self.responses = self
        self.model = configured_model()
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))
        self._states: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def _prepare(self, *, input: Any, previous_response_id: str | None) -> dict[str, Any]:
        if previous_response_id:
            state = self._states.pop(previous_response_id, None)
            if state is None:
                raise RuntimeError("The previous Anthropic response context is no longer available.")
            _append_continuation(state, input)
            return state
        return _initial_state(input)

    def _remember(self, result: Any, state: dict[str, Any]) -> None:
        state["messages"].append({"role": "assistant", "content": result._anthropic_content})
        self._states[result.id] = state
        while len(self._states) > 256:
            self._states.popitem(last=False)


class AnthropicResponsesClient(_AnthropicResponsesBase):
    def __init__(self) -> None:
        super().__init__()
        from anthropic import Anthropic

        self._client = Anthropic()

    def create(
        self,
        *,
        model: str,
        input: Any,
        tools: list[dict[str, Any]] | None = None,
        previous_response_id: str | None = None,
        **_kwargs: Any,
    ) -> Any:
        state = self._prepare(input=input, previous_response_id=previous_response_id)
        request = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=state["messages"],
        )
        if state["system"]:
            request["system"] = state["system"]
        anthropic_tools = _anthropic_tools(tools)
        if anthropic_tools:
            request["tools"] = anthropic_tools
        response = self._client.messages.create(**request)
        result = _compat_response(response)
        self._remember(result, state)
        return result


class AsyncAnthropicResponsesClient(_AnthropicResponsesBase):
    def __init__(self) -> None:
        super().__init__()
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic()

    async def create(
        self,
        *,
        model: str,
        input: Any,
        tools: list[dict[str, Any]] | None = None,
        previous_response_id: str | None = None,
        **_kwargs: Any,
    ) -> Any:
        state = self._prepare(input=input, previous_response_id=previous_response_id)
        request = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=state["messages"],
        )
        if state["system"]:
            request["system"] = state["system"]
        anthropic_tools = _anthropic_tools(tools)
        if anthropic_tools:
            request["tools"] = anthropic_tools
        response = await self._client.messages.create(**request)
        result = _compat_response(response)
        self._remember(result, state)
        return result


def create_responses_client():
    if model_provider() == "anthropic":
        return AnthropicResponsesClient()
    from openai import OpenAI

    return OpenAI()


def create_async_responses_client():
    if model_provider() == "anthropic":
        return AsyncAnthropicResponsesClient()
    from openai import AsyncOpenAI

    return AsyncOpenAI()
