import json

from apps.agent_runtime.mcp.client.mcp_client import mcp_client
from apps.agent_runtime.nodes.execution.tool_selector import tool_selector
from apps.agent_runtime.tools.registry.tool_registry import tool_registry


class TaskExecutor:

    async def execute(self, task: dict, state):

        selected_tool = await tool_selector.select(
            task=task, available_tools=tool_registry.get_all_tools()
        )

        # arguments = json.loads(selected_tool.arguments)

        print(f"Selected tool for task ", selected_tool)

        result = await mcp_client.call_tool(
            # tool_name=selected_tool.name,
            tool_name='users.search_user_details',
            arguments={
                "query": "ayu",
                "agencyId": "df5d452e-9254-45fc-b094-2715d9c26c0e",
                "limit": 10,
            },
            # run_id=state["workflow_id"],
            run_id='3467b548-8117-4cc2-bc68-3ebe471f0163',
            agency_id="df5d452e-9254-45fc-b094-2715d9c26c0e",
            # agency_id=(state["auth_context"].get("agency_id")),
        )

        print("RESULTS:", result)

        return result
