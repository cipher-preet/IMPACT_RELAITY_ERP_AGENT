from typing import Dict
from typing import List
from typing import Optional


class ToolRegistry:

    def __init__(self):

        self._tools: Dict = {}

    def register(self, tools: List[dict]):

        for tool in tools:

            self._tools[tool["name"]] = tool

    def get_tool(self, tool_name: str) -> Optional[dict]:

        return self._tools.get(tool_name)

    def get_all_tools(self):

        return list(self._tools.values())

    def exists(self, tool_name: str):

        return tool_name in self._tools


tool_registry = ToolRegistry()
