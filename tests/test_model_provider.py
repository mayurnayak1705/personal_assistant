import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.embeddings import collection_name, embedding_provider
from app.core.models import (
    _anthropic_tools,
    _append_continuation,
    _append_local_continuation,
    _chat_tools,
    _compat_response,
    _initial_state,
    _local_compat_response,
    configured_model,
    model_provider,
)


class ModelProviderTests(unittest.TestCase):
    def test_explicit_local_provider_needs_no_cloud_key(self):
        environment = {
            "LLM_PROVIDER": "local",
            "LOCAL_LLM_MODEL": "qwen-local",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(model_provider(), "local")
            self.assertEqual(configured_model(), "qwen-local")

    def test_auto_uses_configured_local_model_without_cloud_keys(self):
        with patch.dict(os.environ, {"LOCAL_LLM_MODEL": "local-model"}, clear=True):
            self.assertEqual(model_provider(), "local")

    def test_auto_uses_real_anthropic_key_over_openai_placeholder(self):
        environment = {
            "LLM_PROVIDER": "auto",
            "OPENAI_API_KEY": "replace_with_your_openai_api_key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "EMBEDDING_PROVIDER": "auto",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(model_provider(), "anthropic")
            self.assertEqual(embedding_provider(), "local")
            self.assertEqual(collection_name(), "assistant_memory_local")

    def test_response_tools_are_converted_to_anthropic_schema(self):
        tools = [
            {
                "type": "function",
                "name": "create_task",
                "description": "Create a task",
                "parameters": {"type": "object", "properties": {"title": {"type": "string"}}},
            }
        ]
        converted = _anthropic_tools(tools)
        self.assertEqual(converted[0]["name"], "create_task")
        self.assertEqual(converted[0]["input_schema"], tools[0]["parameters"])

    def test_tool_result_continuation_and_response_compatibility(self):
        state = _initial_state(
            [{"role": "system", "content": "Be concise"}, {"role": "user", "content": "Create it"}]
        )
        _append_continuation(
            state,
            [{"type": "function_call_output", "call_id": "call-1", "output": "created"}],
        )
        self.assertEqual(state["messages"][-1]["content"][0]["type"], "tool_result")

        response = _compat_response(
            SimpleNamespace(
                content=[
                    SimpleNamespace(type="text", text="Done"),
                    SimpleNamespace(type="tool_use", name="create_task", input={"title": "Review"}, id="call-1"),
                ]
            )
        )
        self.assertEqual(response.output_text, "Done")
        self.assertEqual(response.output[1].type, "function_call")
        self.assertEqual(response.output[1].arguments, '{"title": "Review"}')

    def test_local_chat_tools_and_response_compatibility(self):
        tools = [
            {
                "type": "function",
                "name": "create_task",
                "description": "Create a task",
                "parameters": {"type": "object"},
            }
        ]
        self.assertEqual(_chat_tools(tools)[0]["function"]["name"], "create_task")

        response, assistant_message = _local_compat_response(
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Working on it",
                            tool_calls=[
                                SimpleNamespace(
                                    id="call-2",
                                    function=SimpleNamespace(
                                        name="create_task", arguments='{"title":"Review"}'
                                    ),
                                )
                            ],
                        )
                    )
                ]
            )
        )
        self.assertEqual(response.output_text, "Working on it")
        self.assertEqual(response.output[1].call_id, "call-2")
        self.assertEqual(assistant_message["tool_calls"][0]["id"], "call-2")

        state = {"messages": [assistant_message]}
        _append_local_continuation(
            state,
            [{"type": "function_call_output", "call_id": "call-2", "output": "created"}],
        )
        self.assertEqual(state["messages"][-1]["role"], "tool")
        self.assertEqual(state["messages"][-1]["tool_call_id"], "call-2")


if __name__ == "__main__":
    unittest.main()
