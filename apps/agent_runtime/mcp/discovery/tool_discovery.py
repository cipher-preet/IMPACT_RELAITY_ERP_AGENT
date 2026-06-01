
from apps.agent_runtime.mcp.client.mcp_client import mcp_client


class ToolDiscovery:

    async def discover_tools(self):

        response = await mcp_client.list_tools()

        return response["result"]["tools"]
