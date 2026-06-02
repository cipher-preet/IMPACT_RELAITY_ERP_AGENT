from apps.agent_runtime.grpc_runtime.runtime.runtime_manager import (runtime_manager)
from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.runtime.runtime_manager import RuntimeManager


class IntentNode:

    async def run(self, state: GraphState) -> GraphState:

        intent = await runtime_manager.intent_classifier.classify(state["query"])
        state["intent"] = intent

        return state
