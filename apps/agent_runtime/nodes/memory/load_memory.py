import json
from typing import Any

from apps.agent_runtime.state.graph_state import GraphState


class LoadMemoryNode:

    def _safe_json(self, value: Any, default: Any) -> Any:
        if value is None or value == "":
            return default

        if isinstance(value, (dict, list)):
            return value

        try:
            return json.loads(value)
        except Exception:
            return default

    async def run(self, state: GraphState) -> GraphState:

        raw_memory = state.get("memory_context") or {}

        raw_grpc_context = state.get("auth_context") or {}

        memory = {
            "run_id": raw_memory.get("run_id") or raw_grpc_context.get("run_id"),
            "user_id": raw_memory.get("user_id") or raw_grpc_context.get("user_id"),
            "agency_id": raw_memory.get("agency_id")
            or raw_grpc_context.get("agency_id"),
            "session_id": raw_memory.get("session_id")
            or raw_grpc_context.get("session_id"),
            "user_message": (
                raw_memory.get("user_message")
                or raw_grpc_context.get("user_message")
                or state.get("query", "")
            ),
            "summary_memory": (
                raw_memory.get("summary_memory")
                or raw_grpc_context.get("summary_memory")
                or ""
            ),
            "pending_task_context": self._safe_json(
                raw_memory.get("pending_task_context")
                or raw_grpc_context.get("pending_task_context_json"),
                None,
            ),
            "recent_messages": self._safe_json(
                raw_memory.get("recent_messages")
                or raw_grpc_context.get("recent_messages_json"),
                [],
            ),
            "access": self._safe_json(
                raw_memory.get("access") or raw_grpc_context.get("access_json"),
                {},
            ),
        }

        state["query"] = memory["user_message"]

        state["auth_context"] = {
            "run_id": memory["run_id"],
            "user_id": memory["user_id"],
            "agency_id": memory["agency_id"],
            "session_id": memory["session_id"],
            "access": memory["access"],
        }

        state["memory_context"] = memory

        state.setdefault("execution_logs", []).append(
            {
                "node": "LoadMemoryNode",
                "status": "SUCCESS",
                "message": "Memory loaded from gRPC context before planning.",
            }
        )


        return state
