"""Shared cloud/local model selection and Responses compatibility."""

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
    if requested not in {"auto", "openai", "anthropic", "local"}:
        raise ValueError("LLM_PROVIDER must be auto, openai, anthropic, or local.")
    if requested == "openai":
        if not _configured_key("OPENAI_API_KEY"):
            raise RuntimeError("LLM_PROVIDER is openai but OPENAI_API_KEY is not configured.")
        return "openai"
    if requested == "anthropic":
        if not _configured_key("ANTHROPIC_API_KEY"):
            raise RuntimeError("LLM_PROVIDER is anthropic but ANTHROPIC_API_KEY is not configured.")
        return "anthropic"
    if requested == "local":
        return "local"
    if _configured_key("OPENAI_API_KEY"):
        return "openai"
    if _configured_key("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("LOCAL_LLM_MODEL", "").strip():
        return "local"
    raise RuntimeError(
        "Configure OPENAI_API_KEY, ANTHROPIC_API_KEY, or LOCAL_LLM_MODEL; "
        "alternatively set LLM_PROVIDER=local."
    )


def configured_model(default_openai: str = "gpt-4o-mini") -> str:
    provider = model_provider()
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    if provider == "local":
        return os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
    return os.getenv("OPENAI_MODEL", default_openai)


def _local_client_options() -> dict[str, Any]:
    """Connection options shared by local OpenAI-compatible clients."""
    return {
        "base_url": os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/"),
        # The OpenAI SDK requires a value even when the local server ignores it.
        "api_key": os.getenv("LOCAL_LLM_API_KEY", "local"),
        "timeout": float(os.getenv("LOCAL_LLM_TIMEOUT", "120")),
    }


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

    if provider == "local":
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            **_local_client_options(),
        )
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


def _chat_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Convert Responses-style function declarations to Chat Completions tools."""
    output = []
    for tool in tools or []:
        function = tool.get("function", tool)
        output.append(
            {
                "type": "function",
                "function": {
                    "name": function["name"],
                    "description": function.get("description") or "",
                    "parameters": function.get("parameters") or {"type": "object"},
                },
            }
        )
    return output


def _local_initial_state(input_messages: Any) -> dict[str, Any]:
    messages = []
    for message in input_messages if isinstance(input_messages, list) else [input_messages]:
        if isinstance(message, dict):
            messages.append(
                {
                    "role": message.get("role", "user"),
                    "content": message.get("content", ""),
                }
            )
        else:
            messages.append({"role": "user", "content": str(message)})
    return {"messages": messages}


def _append_local_continuation(state: dict[str, Any], continuation: Any) -> None:
    for item in continuation if isinstance(continuation, list) else [continuation]:
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            state["messages"].append(
                {
                    "role": "tool",
                    "tool_call_id": item["call_id"],
                    "content": str(item.get("output", "")),
                }
            )
        elif isinstance(item, dict):
            state["messages"].append(
                {"role": item.get("role", "user"), "content": item.get("content", "")}
            )
        else:
            state["messages"].append({"role": "user", "content": str(item)})


def _local_compat_response(response: Any) -> tuple[Any, dict[str, Any]]:
    message = response.choices[0].message
    text_content = message.content or ""
    output = []
    if text_content:
        output.append(SimpleNamespace(type="message", text=text_content))

    assistant_message: dict[str, Any] = {"role": "assistant", "content": text_content}
    chat_tool_calls = []
    for call in getattr(message, "tool_calls", None) or []:
        call_id = call.id or f"call_{uuid.uuid4().hex}"
        arguments = call.function.arguments or "{}"
        output.append(
            SimpleNamespace(
                type="function_call",
                name=call.function.name,
                arguments=arguments,
                call_id=call_id,
            )
        )
        chat_tool_calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": arguments},
            }
        )
    if chat_tool_calls:
        assistant_message["tool_calls"] = chat_tool_calls

    result = SimpleNamespace(
        id=str(uuid.uuid4()),
        output=output,
        output_text=text_content.strip(),
    )
    return result, assistant_message


class _LocalResponsesBase:
    """Expose the Responses subset used by this app via local Chat Completions."""

    def __init__(self) -> None:
        self.responses = self
        self.model = configured_model()
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))
        self._states: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def _prepare(self, *, input: Any, previous_response_id: str | None) -> dict[str, Any]:
        if previous_response_id:
            state = self._states.pop(previous_response_id, None)
            if state is None:
                raise RuntimeError("The previous local model response context is no longer available.")
            _append_local_continuation(state, input)
            return state
        return _local_initial_state(input)

    def _request(self, state: dict[str, Any], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": state["messages"],
            "max_tokens": self.max_tokens,
        }
        converted_tools = _chat_tools(tools)
        if converted_tools:
            request["tools"] = converted_tools
        return request

    def _remember(self, result: Any, state: dict[str, Any], assistant_message: dict[str, Any]) -> None:
        state["messages"].append(assistant_message)
        self._states[result.id] = state
        while len(self._states) > 256:
            self._states.popitem(last=False)


class LocalResponsesClient(_LocalResponsesBase):
    def __init__(self) -> None:
        super().__init__()
        from openai import OpenAI

        self._client = OpenAI(**_local_client_options())

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
        response = self._client.chat.completions.create(**self._request(state, tools))
        result, assistant_message = _local_compat_response(response)
        self._remember(result, state, assistant_message)
        return result


class AsyncLocalResponsesClient(_LocalResponsesBase):
    def __init__(self) -> None:
        super().__init__()
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(**_local_client_options())

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
        response = await self._client.chat.completions.create(**self._request(state, tools))
        result, assistant_message = _local_compat_response(response)
        self._remember(result, state, assistant_message)
        return result


def create_responses_client():
    provider = model_provider()
    if provider == "anthropic":
        return AnthropicResponsesClient()
    if provider == "local":
        return LocalResponsesClient()
    from openai import OpenAI

    return OpenAI()


def create_async_responses_client():
    provider = model_provider()
    if provider == "anthropic":
        return AsyncAnthropicResponsesClient()
    if provider == "local":
        return AsyncLocalResponsesClient()
    from openai import AsyncOpenAI

    return AsyncOpenAI()
