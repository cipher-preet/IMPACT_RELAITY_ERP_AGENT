from langgraph.graph import StateGraph, END

from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.nodes.reasoning.intent_node import IntentNode
from apps.agent_runtime.nodes.planning.planner_node import PlannerNode
from apps.agent_runtime.nodes.execution.executor_node import ExecutorNode
from apps.agent_runtime.nodes.formatting.response_formatter import ResponseFormatter
from apps.agent_runtime.nodes.human_in_the_loop.human_response_node import (
    HumanResponseNode,
)


class SupervisorGraph:

    @staticmethod
    def route_after_executor(state: GraphState) -> str:

        status = state.get("workflow_status")

        if status == "WAITING_FOR_USER":
            return "human_response"

        if status in ["COMPLETED", "FAILED", "PERMISSION_DENIED", "CANCELLED"]:
            return "response"

        return "executor"

    @staticmethod
    def build():

        graph = StateGraph(GraphState)

        graph.add_node("intent", IntentNode().run)
        graph.add_node("planner", PlannerNode().run)
        graph.add_node("executor", ExecutorNode().run)
        graph.add_node("human_response", HumanResponseNode().run)
        graph.add_node("response", ResponseFormatter().run)

        graph.set_entry_point("intent")

        graph.add_edge("intent", "planner")
        graph.add_edge("planner", "executor")

        graph.add_conditional_edges(
            "executor",
            SupervisorGraph.route_after_executor,
            {
                "executor": "executor",
                "human_response": "human_response",
                "response": "response",
            },
        )

        # IMPORTANT FIX
        graph.add_edge("human_response", "response")
        graph.add_edge("response", END)

        return graph.compile()
