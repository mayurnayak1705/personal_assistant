from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


class ExpenseMCPClient:
    def __init__(self):
        self.server_params = StdioServerParameters(
            command="python",
            args=["mcp/expense/server/server.py"],
        )

    async def call_tool(self, tool_name: str, arguments: dict):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    tool_name,
                    arguments
                )

                return result