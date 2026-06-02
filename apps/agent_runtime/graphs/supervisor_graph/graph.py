from langgraph.graph import StateGraph
from langgraph.graph import END

from apps.agent_runtime.state.graph_state import GraphState

from apps.agent_runtime.nodes.reasoning.intent_node import IntentNode
from apps.agent_runtime.nodes.planning.planner_node import PlannerNode
from apps.agent_runtime.nodes.execution.executor_node import ExecutorNode
from apps.agent_runtime.nodes.formatting.response_formatter import ResponseFormatter


class SupervisorGraph:

    @staticmethod
    def build():

        graph = StateGraph(GraphState)

        graph.add_node("intent", IntentNode().run)

        graph.add_node("planner", PlannerNode().run)

        graph.add_node("executor", ExecutorNode().run)

        graph.add_node("response", ResponseFormatter().run)

        graph.set_entry_point("intent")

        graph.add_edge("intent", "planner")

        graph.add_edge("planner", "executor")

        graph.add_edge("executor", "response")

        graph.add_edge("response", END)

        return graph.compile()
