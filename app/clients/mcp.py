import json
import sys

from mcp import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)

from datetime import datetime
from app.core.debug import debug
from app.core.models import configured_model, create_responses_client
class MCPClient:
    """
    Generic MCP Client.

    Responsible for:
        - Connecting to an MCP Server
        - Discovering available tools
        - Executing GPT tool calls
        - Returning the final LLM response
    """

    def __init__(
        self,
        server_module: str,
        model: str | None = None,
    ):
        self.server_module = server_module
        self.model = model or configured_model("gpt-5")
        self.openai = create_responses_client()

    async def execute(
        self,
        user_input: str,
        system_prompt: str | None = None,
    ) -> str:
        """
        Execute an LLM request using tools exposed
        by an MCP server.
        """
        debug("TOOL", "client_start", integration=self.server_module, model=self.model)
        today = datetime.now()

        date_context = f"""
        Current Date and Time:

        - Today: {today.strftime("%Y-%m-%d")}
        - Current Month: {today.strftime("%B %Y")}
        - Current Year: {today.strftime("%Y")}

        When the user refers to:
        - today
        - yesterday
        - tomorrow
        - this week
        - this month
        - last month
        - this year

        Always resolve them using the current date above before calling tools.
        """
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", self.server_module],
        )

        async with stdio_client(server_params) as (
            read_stream,
            write_stream,
        ):

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:

                await session.initialize()

                ####################################################
                # Discover MCP tools
                ####################################################

                mcp_tools = await session.list_tools()
                import pprint

                # for tool in mcp_tools.tools:
                #     print("=" * 80)
                #     print(tool.name)
                #     pprint.pp(tool.inputSchema)

                openai_tools = []

                for tool in mcp_tools.tools:

                    openai_tools.append(
                        {
                            "type": "function",
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema,
                        }
                    )
                # print(openai_tools)

                ####################################################
                # Build conversation
                ####################################################

                messages = []
                today = datetime.now()

                date_context = f"""
                Current Date and Time:

                - Today: {today.strftime("%Y-%m-%d")}
                - Current Month: {today.strftime("%B %Y")}
                - Current Year: {today.strftime("%Y")}

                When the user refers to:
                - today
                - yesterday
                - tomorrow
                - this week
                - this month
                - last month
                - this year

                Always resolve them using the current date above before calling tools.
                """
                
                if system_prompt:

                    messages.append(
                        {
                            "role": "system",
                            "content": date_context + "\n\n" + system_prompt
                        }
                    )

                messages.append(
                    {
                        "role": "user",
                        "content": user_input,
                    }
                )

                ####################################################
                # First GPT Call
                ####################################################

                response = self.openai.responses.create(
                    model=self.model,
                    input=messages,
                    tools=openai_tools
                )
                # print(f"this is the first response{response}")

                ####################################################
                # Continue until no tool calls remain
                ####################################################

                while True:
                    tool_calls = [
                        item
                        for item in response.output
                        if item.type == "function_call"
                    ]
                    if not tool_calls:
                        return response.output_text

                    tool_outputs = []

                    for tool_call in tool_calls:
                        arguments = json.loads(
                            tool_call.arguments
                        )

                        debug("TOOL", "call", integration=self.server_module,
                              tool=tool_call.name, parameters=arguments)

                        result = await session.call_tool(
                            tool_call.name,
                            arguments,
                        )

                        if result.content:
                            output = result.content[0].text

                        else:
                            output = ""

                        debug("TOOL", "result", integration=self.server_module,
                              tool=tool_call.name,
                              is_error=bool(getattr(result, "isError", False)),
                              output_chars=len(output))
                        tool_outputs.append(
                            {
                                "type": "function_call_output",
                                "call_id": tool_call.call_id,
                                "output": output,
                            }
                        )
                        # print(tool_outputs)
                    response = self.openai.responses.create(
                        model=self.model,
                        previous_response_id=response.id,
                        input=tool_outputs,
                        tools=openai_tools,   # <-- add this
                    )
