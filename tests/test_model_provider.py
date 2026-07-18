import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from embedding_provider import collection_name, embedding_provider
from model_provider import (
    _anthropic_tools,
    _append_continuation,
    _compat_response,
    _initial_state,
    model_provider,
)


class ModelProviderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
