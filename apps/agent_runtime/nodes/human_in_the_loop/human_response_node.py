from apps.agent_runtime.state.graph_state import GraphState


class HumanResponseNode:

    async def run(self, state: GraphState) -> GraphState:

        pending = state.get("pending_clarifications", [])

        print(f"Pending human inputs: (((((((((((((( {pending}")

        latest = pending[-1] if pending else None

        print(f"Latest human input: ))))))))))))))))))) {latest}")

        state["final_response"] = {
            "success": True,
            "workflow_id": state.get("workflow_id"),
            "status": "WAITING_FOR_USER",
            "requires_human_input": True,
            "human_input": latest,
        }

        return state
