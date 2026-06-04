from apps.agent_runtime.tools.registry.tool_registry import tool_registry

from apps.agent_runtime.tools.registry.capability_registry import CapabilityRegistry

from apps.agent_runtime.mcp.discovery.tool_discovery import ToolDiscovery


class RuntimeManager:

    def __init__(self):

        # self.tool_registry = ToolRegistry()

        self.capability_registry = CapabilityRegistry()

        self.discovery = ToolDiscovery()

    async def initialize(self):

        await self.load_tools()

    async def load_tools(self):

        tools = await self.discovery.discover_tools()
        
        for tool in tools:
            
            
            print(f" - {tool['name']}")

        tool_registry.register(tools)

        self.capability_registry.build(tools)

    async def shutdown(self):

        print("Runtime Shutdown")
