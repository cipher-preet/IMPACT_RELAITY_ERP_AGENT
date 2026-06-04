from datetime import datetime
from typing import Dict, Any


class HITLBuilder:

    @staticmethod
    def build_from_task(task: Dict[str, Any]) -> Dict[str, Any]:

        action = task.get("action")

        if action in ["REQUEST_CLARIFICATION", "CLARIFY"]:

            return {
                "requires_human_input": True,
                "status": "WAITING_FOR_USER",
                "human_input": {
                    "id": f"hitl_{task['task_id']}",
                    "type": "CLARIFICATION",
                    "task_id": task["task_id"],
                    "message": task.get(
                        "description", "Please provide clarification to continue."
                    ),
                    "options": [],
                    "required_fields": task.get("required_entities", []),
                    "metadata": {"task": task},
                    "status": "PENDING",
                    "created_at": datetime.utcnow().isoformat(),
                },
            }

        if action in ["REQUEST_APPROVAL", "APPROVE"]:

            return {
                "requires_human_input": True,
                "status": "WAITING_FOR_USER",
                "human_input": {
                    "id": f"hitl_{task['task_id']}",
                    "type": "APPROVAL",
                    "task_id": task["task_id"],
                    "message": task.get(
                        "description", "Approval is required before continuing."
                    ),
                    "options": [
                        {"label": "Approve", "value": "APPROVED"},
                        {"label": "Reject", "value": "REJECTED"},
                    ],
                    "required_fields": [],
                    "metadata": {"task": task},
                    "status": "PENDING",
                    "created_at": datetime.utcnow().isoformat(),
                },
            }

        return {}
