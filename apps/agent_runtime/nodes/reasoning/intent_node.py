from apps.agent_runtime.grpc_runtime.runtime.runtime_manager import (runtime_manager)
from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.runtime.progress_events import emit_progress


class IntentNode:

    def _readable(self, value) -> str:
        raw_value = getattr(value, "value", value)

        return str(raw_value or "").replace("_", " ").strip().lower()

    def _intent_message(self, intent) -> str:
        action = self._readable(getattr(intent, "action", ""))
        module = self._readable(getattr(intent, "module", ""))
        domain = self._readable(getattr(intent, "domain", ""))

        if action and module and action != "general":
            message = f"You asked me to {action} something in {module}. I am checking what information and steps are needed."
        elif module and module != "general":
            message = f"I recognized this as a {module} request. I am checking what needs to happen next."
        elif domain and domain != "general":
            message = f"I recognized the request area as {domain}. I am checking the best way to handle it."
        else:
            message = "I understood your request. I am checking what needs to happen next."

        if getattr(intent, "requires_clarification", False):
            return f"{message} It may need one more detail before I can continue."

        if getattr(intent, "requires_approval", False):
            return f"{message} This may require confirmation before I take action."

        return message

    async def run(self, state: GraphState) -> GraphState:

        intent = await runtime_manager.intent_classifier.classify(state["query"])
        state["intent"] = intent

        emit_progress(
            state,
            "thinking",
            self._intent_message(intent),
            {
                "stage": "intent_classified",
                "intent": intent.model_dump()
                if hasattr(intent, "model_dump")
                else intent,
            },
        )

        return state
