from apps.agent_runtime.state.graph_state import GraphState


class ResponseFormatter:

    async def run(self, state: GraphState) -> GraphState:

        if state.get("workflow_status") == "WAITING_FOR_USER":

            human_input = state.get("pending_human_input")

            state["final_response"] = {
                "success": True,
                "workflow_id": state.get("workflow_id"),
                "status": "WAITING_FOR_USER",
                "requires_human_input": True,
                "message": (
                    human_input.get("message", "Human input is required to continue.")
                    if human_input
                    else "Human input is required to continue."
                ),
                "human_input": human_input,
                "options": human_input.get("options", []) if human_input else [],
            }

            return state

        if state.get("workflow_status") == "FAILED":

            state["final_response"] = {
                "success": False,
                "workflow_id": state.get("workflow_id"),
                "status": "FAILED",
                "errors": state.get("failed_tasks", []),
                "task_results": state.get("task_results", {}),
            }

            return state

        state["final_response"] = {
            "success": True,
            "workflow_id": state.get("workflow_id"),
            "status": "COMPLETED",
            "data": state.get("task_results", {}),
        }

        return state
