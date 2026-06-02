from apps.agent_runtime.state.graph_state import GraphState


class ResponseFormatter:

    async def run(self, state: GraphState) -> GraphState:

        state["task_results"]["summary"] = {
            "workflow_id": state["workflow_id"],
            "completed": len(state["completed_tasks"]),
            "failed": len(state["failed_tasks"]),
            "status": state["workflow_status"],
        }

        return state
