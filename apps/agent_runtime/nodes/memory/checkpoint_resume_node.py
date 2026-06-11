import json
from typing import Any, Dict, Optional

from apps.agent_runtime.llms.openai.openai_client import openai_llm


from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.agents.schemas.memory.checkpoint_resume_schema import (
    CheckpointResumeDecision,
)
from apps.agent_runtime.agents.prompts.memory.checkpoint_resume_prompt import (
    checkpoint_resume_prompt,
)


class CheckpointResumeNode:

    def __init__(self):

        structured_llm = openai_llm.with_structured_output(CheckpointResumeDecision, method="function_calling",)
        self.chain = checkpoint_resume_prompt | structured_llm

    def _selected_payload_data(
        self,
        resolved_payload: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(resolved_payload, dict):
            return None

        for key, value in resolved_payload.items():
            if not str(key).startswith("selected_") or not isinstance(value, dict):
                continue

            metadata = value.get("metadata")

            if isinstance(metadata, dict):
                selected_data = dict(metadata)
            else:
                selected_data = dict(value)

            for field in ("id", "type", "label", "confidence"):
                if field in value and field not in selected_data:
                    selected_data[field] = value[field]

            return selected_data

        return None

    def _apply_resolved_payload_result(
        self,
        state: GraphState,
        task_id: str,
        selected_data: Dict[str, Any],
    ) -> GraphState:
        state.setdefault("task_results", {})
        state.setdefault("completed_tasks", [])
        state.setdefault("execution_logs", [])

        state["task_results"][task_id] = {
            "result": {
                "structuredContent": {
                    "status": "success",
                    "message": "Here are the details I found.",
                    "data": selected_data,
                }
            }
        }

        if task_id not in state["completed_tasks"]:
            state["completed_tasks"].append(task_id)

        state["current_task_id"] = task_id
        state["workflow_status"] = "COMPLETED"
        state["waiting_for_user_input"] = False
        state["pending_human_input"] = None

        state["execution_logs"].append(
            {
                "node": "CheckpointResumeNode",
                "status": "ANSWERED_FROM_PENDING_CONTEXT",
                "task_id": task_id,
            }
        )

        return state

    async def run(self, state: GraphState) -> GraphState:
        memory = state.get("memory_context") or {}

        pending_task_context = memory.get("pending_task_context")
        recent_messages = memory.get("recent_messages", [])
        latest_user_message = memory.get("user_message") or state.get("query", "")
        summary_memory = memory.get("summary_memory", "")

        if not pending_task_context:
            state["resume_context"] = None
            state["workflow_status"] = "RUNNING"

            state.setdefault("execution_logs", []).append(
                {
                    "node": "CheckpointResumeNode",
                    "status": "NO_PENDING_CONTEXT",
                }
            )

            return state

        decision: CheckpointResumeDecision = await self.chain.ainvoke(
            {
                "latest_user_message": latest_user_message,
                "summary_memory": summary_memory,
                "recent_messages": json.dumps(
                    recent_messages,
                    ensure_ascii=False,
                ),
                "pending_task_context": json.dumps(
                    pending_task_context,
                    ensure_ascii=False,
                ),
            }
        )
        
        print("this is checkpoint decision print ----^^^^^^^^^^^^^^^^  ", decision)

        if decision.can_resume and not decision.needs_user_input:
            state["resume_context"] = {
                "can_resume": True,
                "resume_type": decision.resume_type,
                "task_id": decision.task_id,
                "resolved_payload": decision.resolved_payload,
                "reason": decision.reason,
                "pending_task_context": pending_task_context,
            }

            state.setdefault("execution_context", {})
            state["execution_context"]["resume_context"] = state["resume_context"]

            state["waiting_for_user_input"] = False
            state["pending_human_input"] = None
            state["workflow_status"] = "RUNNING"

            state.setdefault("execution_logs", []).append(
                {
                    "node": "CheckpointResumeNode",
                    "status": "RESOLVED",
                    "resume_type": decision.resume_type,
                    "reason": decision.reason,
                }
            )

            selected_data = self._selected_payload_data(decision.resolved_payload)

            if decision.resume_type == "selection" and selected_data:
                return self._apply_resolved_payload_result(
                    state=state,
                    task_id=decision.task_id or "resolved_selection",
                    selected_data=selected_data,
                )

            return state

        state["resume_context"] = {
            "can_resume": False,
            "resume_type": decision.resume_type,
            "reason": decision.reason,
            "pending_task_context": pending_task_context,
        }

        state["waiting_for_user_input"] = True
        state["workflow_status"] = "WAITING_FOR_USER"
        state["pending_human_input"] = {
            "type": "follow_up_question",
            "message": decision.user_question or "Please clarify your response.",
            "payload": pending_task_context,
        }

        state.setdefault("execution_logs", []).append(
            {
                "node": "CheckpointResumeNode",
                "status": "WAITING_FOR_USER",
                "reason": decision.reason,
            }
        )

        return state
