from datetime import datetime
from typing import Dict, Any


class HITLBuilder:

    @staticmethod
    def build_from_task(task: Dict[str, Any]) -> Dict[str, Any]:

        action = str(task.get("action", "")).upper()
        module = str(task.get("module", "")).upper()

        task_id = task["task_id"]

        is_clarification = (
            "CLARIFICATION" in action
            or "CLARIFY" in action
            or module == "CLARIFICATION"
        )

        is_approval = (
            "APPROVAL" in action or module == "APPROVAL" or module == "HUMAN_APPROVAL"
        )

        if is_approval:

            hitl_type = "APPROVAL"

            options = [
                {
                    "label": "Approve",
                    "value": "APPROVED",
                },
                {
                    "label": "Reject",
                    "value": "REJECTED",
                },
            ]

        elif is_clarification:

            hitl_type = "CLARIFICATION"
            options = []

        else:

            hitl_type = "HUMAN_INPUT"
            options = []

        return {
            "requires_human_input": True,
            "status": "WAITING_FOR_USER",
            "human_input": {
                "id": f"hitl_{task_id}",
                "type": hitl_type,
                "task_id": task_id,
                "message": task.get(
                    "description",
                    "Human input is required to continue.",
                ),
                "options": options,
                "required_fields": task.get("required_entities", []),
                "metadata": {
                    "task": task,
                },
                "status": "PENDING",
                "created_at": datetime.utcnow().isoformat(),
            },
        }
