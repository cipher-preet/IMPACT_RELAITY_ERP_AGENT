from apps.agent_runtime.agents.executor.argument_generator import argument_generator
from apps.agent_runtime.mcp.client.mcp_client import mcp_client
from apps.agent_runtime.nodes.execution.tool_selector import tool_selector
from apps.agent_runtime.tools.registry.tool_registry import tool_registry


class TaskExecutor:

    async def execute(self, task: dict, state):

        auth_context = state.get("auth_context", {})
        
        print("htis is auth contect print", auth_context)

        selected_tool = await tool_selector.select(
            task=task, available_tools=tool_registry.get_all_tools()
        )

        get_tool_info = tool_registry.get_tool(selected_tool.name)

        generated_arguments = await argument_generator.generate_arguments(
            query=state.get("query"),
            tool_name=selected_tool.name,
            tool_schema=get_tool_info.get("inputSchema"),
            resolved_entities=state.get("resolved_entities", {}),
            auth_context=auth_context,
        )

        print("this is selcted tool name ----->>> ", selected_tool.name)

        result = await mcp_client.call_tool(
            tool_name=selected_tool.name,
            arguments=generated_arguments["arguments"],
            run_id=auth_context.get("run_id"),
            agency_id=auth_context.get("agency_id"),
        )

        return result
