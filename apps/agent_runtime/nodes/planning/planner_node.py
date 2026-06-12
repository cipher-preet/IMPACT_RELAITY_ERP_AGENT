from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.agents.planner.decomposition import decomposer


class PlannerNode:

    async def run(self, state: GraphState) -> GraphState:

        workflow_plan = await decomposer.decompose(
            query=state["query"],
            intent=state["intent"],
            memory_context=state.get("memory_context", {}),
        )

        state["workflow_id"] = workflow_plan.workflow_id

        state["workflow_plan"] = workflow_plan.model_dump()

        state["workflow_status"] = "PLANNED"

        return state
