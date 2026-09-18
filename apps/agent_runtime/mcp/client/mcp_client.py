import uuid
import re
import logging
import httpx

from typing import Any
from typing import Dict
from typing import Optional

from apps.api_gateway.config.setting import settings

logger = logging.getLogger(__name__)


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

            try:
                response = await client.post(
                    self.base_url, json=payload, headers=self._headers()
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "MCP initialize failed status=%s body=%s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise
            except httpx.HTTPError:
                logger.exception("MCP initialize request failed base_url=%s", self.base_url)
                raise

            return response.json()

    async def list_tools(self):

        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            try:
                response = await client.post(
                    self.base_url, json=payload, headers=self._headers()
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "MCP list_tools failed status=%s body=%s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise
            except httpx.HTTPError:
                logger.exception("MCP list_tools request failed base_url=%s", self.base_url)
                raise

            return response.json()

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        run_id: str,
        agency_id: Optional[str] = None,
        confirmed: bool = False,
    ):

        arguments = dict(arguments or {})

        if agency_id and not any(
            str(key).replace("_", "").lower() == "agencyid"
            for key in arguments
        ):
            arguments["agencyId"] = agency_id

        tool_tokens = {
            token.lower()
            for token in re.split(r"[^a-zA-Z0-9]+", str(tool_name or ""))
            if token
        }

        if agency_id and "agency" in tool_tokens and not any(
            str(key).replace("_", "").lower() in {"id", "uuid", "agencyid"}
            for key in arguments
        ):
            arguments["id"] = agency_id

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

            try:
                logger.info(
                    "Calling MCP tool tool_name=%s run_id=%s agency_id=%s arguments=%s",
                    tool_name,
                    run_id,
                    agency_id,
                    arguments,
                )
                response = await client.post(
                    self.base_url, json=payload, headers=self._headers()
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "MCP tool call failed tool_name=%s run_id=%s status=%s body=%s",
                    tool_name,
                    run_id,
                    exc.response.status_code,
                    exc.response.text,
                )
                raise
            except httpx.HTTPError:
                logger.exception(
                    "MCP tool call request failed tool_name=%s run_id=%s base_url=%s",
                    tool_name,
                    run_id,
                    self.base_url,
                )
                raise

            try:
                result = response.json()
            except ValueError:
                logger.exception(
                    "MCP tool call returned invalid JSON tool_name=%s run_id=%s body=%s",
                    tool_name,
                    run_id,
                    response.text,
                )
                raise

            if isinstance(result, dict) and result.get("error"):
                logger.error(
                    "MCP tool call returned JSON-RPC error tool_name=%s run_id=%s error=%s",
                    tool_name,
                    run_id,
                    result.get("error"),
                )

            return result


mcp_client = MCPClient(
    base_url=settings.NODE_MCP_SERVER_URL, token=settings.ASSISTANT_MCP_SERVER_TOKEN
)
