from mcp import ClientSession
from mcp.client.stdio import stdio_client

class MemoryToolExecutor:

    async def call_tool(self, tool_name: str, arguments: dict):

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "Server.server"],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                return await session.call_tool(
                    tool_name,
                    arguments,
                )