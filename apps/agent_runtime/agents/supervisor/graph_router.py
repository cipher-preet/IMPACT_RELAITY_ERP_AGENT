from apps.agent_runtime.agents.schemas.supervisor.intent_classifier_schema import (
    DomainEnum,
    IntentClassifierResponse,
)


class GraphRouter:

    GRAPH_MAPPING = {
        DomainEnum.ERP: "erp_graph",
        DomainEnum.ANALYTICS: "analytics_graph",
        DomainEnum.COMMUNICATION: "communication_graph",
        DomainEnum.AUTOMATION: "automation_graph",
        DomainEnum.RETRIEVAL: "retrieval_graph",
        DomainEnum.SUPPORT: "support_graph",
        DomainEnum.GOVERNANCE: "governance_graph",
        DomainEnum.GENERAL: "supervisor_graph",
    }

    async def route(self, intent: IntentClassifierResponse) -> dict:

        selected_graph = self.GRAPH_MAPPING.get(intent.domain, "supervisor_graph")

        return {
            "graph": selected_graph,
            "entry_node": self._resolve_entry_node(intent),
            "requires_clarification": intent.requires_clarification,
            "requires_approval": intent.requires_approval,
            "execution_type": intent.execution_type,
        }

    def _resolve_entry_node(self, intent: IntentClassifierResponse) -> str:

        if intent.requires_clarification:
            return "clarification_node"

        if intent.requires_approval:
            return "approval_node"

        return "memory_loader_node"


graph_router = GraphRouter()
