import os

from apps.agent_runtime.mcp.client.mcp_client import MCPClient

mcp_client = MCPClient(
    base_url=os.getenv("NODE_MCP_SERVER_URL"),
    token=os.getenv("ASSISTANT_MCP_SERVER_TOKEN "),
)
