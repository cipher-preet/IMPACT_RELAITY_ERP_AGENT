import json
from typing import Any, Dict, List, Optional


class GrpcMemoryNormalizer:
    @staticmethod
    def safe_json_loads(value: Optional[str], default: Any) -> Any:
        if not value:
            return default

        if isinstance(value, (dict, list)):
            return value

        try:
            return json.loads(value)
        except Exception:
            return default

    def normalize(self, grpc_payload: Dict[str, Any]) -> Dict[str, Any]:
        pending_context = self.safe_json_loads(
            grpc_payload.get("pending_task_context_json"),
            None,
        )

        recent_messages = self.safe_json_loads(
            grpc_payload.get("recent_messages_json"),
            [],
        )

        access = self.safe_json_loads(
            grpc_payload.get("access_json"),
            {},
        )

        return {
            "run_id": grpc_payload.get("run_id"),
            "user_id": grpc_payload.get("user_id"),
            "agency_id": grpc_payload.get("agency_id"),
            "session_id": grpc_payload.get("session_id"),
            "user_message": grpc_payload.get("user_message", ""),
            "summary_memory": grpc_payload.get("summary_memory", ""),
            "pending_task_context": pending_context,
            "recent_messages": recent_messages,
            "access": access,
        }
