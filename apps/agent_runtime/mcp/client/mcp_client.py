import uuid
import httpx

from typing import Any
from typing import Dict
from typing import Optional

from apps.api_gateway.config.setting import settings


class MCPClient:

    def __init__(self, base_url: str, token: str, timeout: int = 30):

        self.base_url = base_url
        self.token = token
        self.timeout = timeout

    def _headers(self):

        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def initialize(self):

        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            response = await client.post(
                self.base_url, json=payload, headers=self._headers()
            )

            response.raise_for_status()

            return response.json()

    async def list_tools(self):

        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            response = await client.post(
                self.base_url, json=payload, headers=self._headers()
            )

            response.raise_for_status()

            return response.json()

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        run_id: str,
        agency_id: Optional[str] = None,
        confirmed: bool = False,
    ):


        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
                "_meta": {
                    "runId": run_id,
                    "agencyId": agency_id,
                    "confirmed": confirmed,
                },
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            response = await client.post(
                self.base_url, json=payload, headers=self._headers()
            )
            response.raise_for_status()

            return response.json()


mcp_client = MCPClient(
    base_url=settings.NODE_MCP_SERVER_URL, token=settings.ASSISTANT_MCP_SERVER_TOKEN
)
