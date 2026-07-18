import json
import sys
from datetime import datetime

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from working_context import ToolExecutionResult, build_tool_event
from debug_log import debug
from model_provider import configured_model, create_responses_client


class ExpenseMCPClient:
    """Expense-specific MCP client that preserves structured report artifacts."""

    def __init__(self, model=None):
        self.model = model or configured_model("gpt-4o-mini")
        self.openai = create_responses_client()
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_servers.expense.server.main"],
        )

    @staticmethod
    def _parse_artifact(output):
        try:
            value = json.loads(output)
        except (TypeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) and value.get("artifact_type") == "expense_report" else None

    async def execute(self, user_input, system_prompt=None):
        today = datetime.now()
        date_context = f"""
Current date: {today:%Y-%m-%d}
Current month: {today:%B %Y}
Current year: {today:%Y}
Resolve relative dates such as today, this week, this month, and this year before calling tools.
"""
        async with stdio_client(self.server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                discovered = await session.list_tools()
                tools = [
                    {
                        "type": "function",
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                    for tool in discovered.tools
                ]
                messages = [
                    {"role": "system", "content": date_context + "\n" + (system_prompt or "")},
                    {"role": "user", "content": user_input},
                ]
                response = self.openai.responses.create(model=self.model, input=messages, tools=tools)
                artifact = None
                events = []

                while True:
                    calls = [item for item in response.output if item.type == "function_call"]
                    if not calls:
                        return ToolExecutionResult(
                            text=response.output_text,
                            events=events,
                            artifact=artifact,
                        )

                    outputs = []
                    for call in calls:
                        arguments = json.loads(call.arguments)
                        debug("TOOL", "call", integration="expenses", tool=call.name, parameters=arguments)
                        result = await session.call_tool(call.name, arguments)
                        output = "\n".join(
                            block.text for block in result.content if hasattr(block, "text")
                        ) if result.content else ""
                        parsed_artifact = self._parse_artifact(output)
                        debug("TOOL", "result", integration="expenses", tool=call.name,
                              is_error=bool(getattr(result, "isError", False)), output_chars=len(output))
                        if parsed_artifact:
                            artifact = parsed_artifact
                        events.append(
                            build_tool_event(
                                integration="expenses",
                                tool_name=call.name,
                                arguments=arguments,
                                output=output,
                                is_error=bool(getattr(result, "isError", False)),
                            )
                        )
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": output,
                        })
                    response = self.openai.responses.create(
                        model=self.model,
                        previous_response_id=response.id,
                        input=outputs,
                        tools=tools,
                    )


expense_client = ExpenseMCPClient()
