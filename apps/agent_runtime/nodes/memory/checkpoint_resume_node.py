import json
import re
from typing import Any, Dict, Optional

from apps.agent_runtime.llms.openai.openai_client import openai_llm


from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.agents.schemas.memory.checkpoint_resume_schema import (
    CheckpointResumeDecision,
    ConfirmationDecision,
)
from apps.agent_runtime.agents.prompts.memory.checkpoint_resume_prompt import (
    checkpoint_resume_prompt,
)
from apps.agent_runtime.agents.prompts.memory.confirmation_decision_prompt import (
    confirmation_decision_prompt,
)
from apps.agent_runtime.tools.registry.tool_registry import tool_registry


class CheckpointResumeNode:

    def __init__(self):

        structured_llm = openai_llm.with_structured_output(
            CheckpointResumeDecision,
            method="function_calling",
        )
        self.chain = checkpoint_resume_prompt | structured_llm
        confirmation_llm = openai_llm.with_structured_output(
            ConfirmationDecision,
            method="function_calling",
        )
        self.confirmation_chain = confirmation_decision_prompt | confirmation_llm

    def _available_business_tools(self) -> list:
        return [
            tool
            for tool in tool_registry.get_all_tools()
            if not str(tool.get("name", "")).startswith("assistant.")
        ]

    async def _classify_confirmation_response(
        self,
        latest_user_message: str,
        pending_task_context: Dict[str, Any],
        recent_messages: Any,
    ) -> ConfirmationDecision:
        return await self.confirmation_chain.ainvoke(
            {
                "latest_user_message": latest_user_message,
                "pending_task_context": json.dumps(
                    pending_task_context,
                    default=str,
                    ensure_ascii=False,
                ),
                "recent_messages": json.dumps(
                    recent_messages,
                    default=str,
                    ensure_ascii=False,
                ),
            }
        )

    def _find_pending_tool_context(
        self,
        value: Any,
    ) -> Optional[Dict[str, Any]]:
        if isinstance(value, dict):
            data = value.get("data")

            if isinstance(data, dict) and data.get("tool_name"):
                return {
                    "tool_name": data.get("tool_name"),
                    "missing_fields": data.get("missing_fields") or [],
                    "provided_arguments": data.get("provided_arguments") or {},
                    "task_id": value.get("task_id"),
                    "message": value.get("message"),
                    "confirmation_required": self._has_confirmation(value),
                }

            if value.get("tool_name"):
                return {
                    "tool_name": value.get("tool_name"),
                    "missing_fields": value.get("missing_fields") or [],
                    "provided_arguments": value.get("provided_arguments") or {},
                    "task_id": value.get("task_id"),
                    "message": value.get("message"),
                    "confirmation_required": self._has_confirmation(value),
                }

            for child in value.values():
                found = self._find_pending_tool_context(child)

                if found:
                    if not found.get("task_id") and value.get("task_id"):
                        found["task_id"] = value.get("task_id")

                    if self._has_confirmation(value):
                        found["confirmation_required"] = True

                    return found

        if isinstance(value, list):
            for child in value:
                found = self._find_pending_tool_context(child)

                if found:
                    return found

        return None

    def _has_confirmation(self, value: Any) -> bool:
        if not isinstance(value, dict):
            return False

        waiting_for = str(
            value.get("waitingFor")
            or value.get("event_type")
            or value.get("eventType")
            or value.get("type")
            or ""
        ).lower()

        if waiting_for == "confirmation_required":
            return True

        if value.get("confirmationRequired") is True:
            return True

        status = str(value.get("status") or "").lower()

        if status == "requires_confirmation":
            return True

        for child in value.values():
            if isinstance(child, dict) and self._has_confirmation(child):
                return True

            if isinstance(child, list):
                for item in child:
                    if isinstance(item, dict) and self._has_confirmation(item):
                        return True

        return False

    def _is_confirmation_resume_type(self, resume_type: str) -> bool:
        return (
            "confirm" in str(resume_type or "").lower()
            or "approval" in str(resume_type or "").lower()
        )

    def _clean_field_value(self, field_name: str, message: str) -> str:
        value = str(message or "").strip()

        patterns = [
            rf"^\s*{re.escape(field_name)}\s*(?:is|=|:)\s*",
            rf"^\s*[\w\s-]+?\s+{re.escape(field_name)}\s*(?:is|=|:)?\s*",
        ]

        for pattern in patterns:
            value = re.sub(pattern, "", value, flags=re.IGNORECASE).strip()

        value = re.split(
            r"\s+(?:used\s+for|for\s+purpose\s+of|purpose\s+is)\s+",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

        return value.strip(" .'\"")

    def _deterministic_missing_input_payload(
        self,
        latest_user_message: str,
        pending_tool_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not pending_tool_context:
            return None

        tool_name = str(pending_tool_context.get("tool_name") or "")

        if tool_name.startswith("assistant."):
            return None

        missing_fields = pending_tool_context.get("missing_fields") or []

        if len(missing_fields) != 1:
            return None

        field_name = str(missing_fields[0])
        value = self._clean_field_value(field_name, latest_user_message)

        if not value:
            return None

        return {field_name: value}

    def _tool_schema_properties(self, tool_name: str) -> Dict[str, Any]:
        tool = tool_registry.get_tool(tool_name) or {}
        schema = tool.get("inputSchema") or {}
        properties = schema.get("properties") or {}

        return properties if isinstance(properties, dict) else {}

    def _tool_required_fields(self, tool_name: str) -> list:
        tool = tool_registry.get_tool(tool_name) or {}
        schema = tool.get("inputSchema") or {}
        required = schema.get("required") or []

        return required if isinstance(required, list) else []

    def _auth_arguments_for_tool(
        self,
        tool_name: str,
        memory: Dict[str, Any],
    ) -> Dict[str, Any]:
        properties = self._tool_schema_properties(tool_name)
        auth_values = {
            "agencyid": memory.get("agency_id"),
            "userid": memory.get("user_id"),
            "runid": memory.get("run_id"),
            "sessionid": memory.get("session_id"),
        }
        arguments = {}

        for field_name in properties:
            normalized = str(field_name).replace("_", "").lower()
            value = auth_values.get(normalized)

            if value not in (None, ""):
                arguments[field_name] = value

        return arguments

    def _build_pending_tool_context_from_decision(
        self,
        decision: CheckpointResumeDecision,
        pending_tool_context: Optional[Dict[str, Any]],
        memory: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        pending_tool_name = (pending_tool_context or {}).get("tool_name")
        tool_name = decision.tool_name or pending_tool_name

        if not tool_name or not tool_registry.exists(tool_name):
            return None

        if str(tool_name).startswith("assistant."):
            return None

        if (
            str(pending_tool_name or "").startswith("assistant.")
            and not decision.tool_name
        ):
            return None

        provided_arguments = dict(
            (pending_tool_context or {}).get("provided_arguments") or {}
        )
        provided_arguments.update(self._auth_arguments_for_tool(tool_name, memory))

        resolved_payload = decision.resolved_payload or {}
        required_fields = self._tool_required_fields(tool_name)
        missing_fields = [
            field
            for field in required_fields
            if field not in provided_arguments and field not in resolved_payload
        ]
        resolved_fields = [
            field
            for field in required_fields
            if field in resolved_payload and field not in provided_arguments
        ]

        return {
            "tool_name": tool_name,
            "missing_fields": missing_fields or resolved_fields,
            "provided_arguments": provided_arguments,
            "task_id": (
                decision.task_id
                or (pending_tool_context or {}).get("task_id")
                or "resumed_tool_task"
            ),
            "message": (pending_tool_context or {}).get("message"),
            "confirmation_required": (pending_tool_context or {}).get(
                "confirmation_required",
                False,
            )
            or self._is_confirmation_resume_type(decision.resume_type),
        }

    def _value_for_missing_field(
        self,
        field_name: str,
        resolved_payload: Optional[Dict[str, Any]],
    ) -> Any:
        if not isinstance(resolved_payload, dict):
            return None

        if field_name in resolved_payload:
            return resolved_payload[field_name]

        normalized_field = field_name.lower()

        for key, value in resolved_payload.items():
            normalized_key = str(key).lower()

            if normalized_key == normalized_field:
                return value

            if normalized_key.endswith(f"_{normalized_field}"):
                return value

            if normalized_field in normalized_key:
                return value

        if len(resolved_payload) == 1:
            return next(iter(resolved_payload.values()))

        return None

    def _build_resume_tool_arguments(
        self,
        pending_tool_context: Dict[str, Any],
        resolved_payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        arguments = dict(pending_tool_context.get("provided_arguments") or {})

        for field_name in pending_tool_context.get("missing_fields") or []:
            value = self._value_for_missing_field(field_name, resolved_payload)

            if value not in (None, ""):
                arguments[field_name] = value

        return arguments

    def _apply_tool_resume_plan(
        self,
        state: GraphState,
        pending_tool_context: Dict[str, Any],
        resolved_payload: Dict[str, Any],
        reason: str,
        confirmed: bool = False,
    ) -> GraphState:
        task_id = pending_tool_context.get("task_id") or "resumed_task"
        tool_name = pending_tool_context["tool_name"]
        arguments = self._build_resume_tool_arguments(
            pending_tool_context=pending_tool_context,
            resolved_payload=resolved_payload,
        )

        state["resume_context"] = {
            "can_resume": True,
            "resume_type": "missing_input",
            "task_id": task_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "resolved_payload": resolved_payload,
            "pending_tool_context": pending_tool_context,
            "reason": reason,
            "confirmed": confirmed,
        }

        state["workflow_plan"] = {
            "workflow_id": state.get("workflow_id") or "resumed_workflow",
            "tasks": [
                {
                    "task_id": task_id,
                    "domain": "ERP",
                    "module": "RESUMED_TOOL",
                    "action": "EXECUTE",
                    "description": reason or f"Resume {tool_name}",
                    "dependencies": [],
                    "execution_order": 1,
                    "required_entities": [],
                    "assigned_graph": state.get("active_graph"),
                    "status": "PENDING",
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "confirmed": confirmed,
                }
            ],
        }
        state["workflow_status"] = "PLANNED"
        state["waiting_for_user_input"] = False
        state["pending_human_input"] = None
        state.setdefault("execution_context", {})
        state["execution_context"]["resume_context"] = state["resume_context"]
        state.setdefault("execution_logs", []).append(
            {
                "node": "CheckpointResumeNode",
                "status": "RESUMED_TOOL_CALL",
                "tool_name": tool_name,
                "task_id": task_id,
            }
        )

        return state

    def _cancel_pending_confirmation(
        self,
        state: GraphState,
        pending_task_context: Dict[str, Any],
    ) -> GraphState:
        state["workflow_status"] = "COMPLETED"
        state["waiting_for_user_input"] = False
        state["pending_human_input"] = None
        state.setdefault("task_results", {})
        state["task_results"]["confirmation_cancelled"] = {
            "result": {
                "structuredContent": {
                    "status": "success",
                    "message": "Okay, I will not proceed with that action.",
                    "data": {
                        "cancelled": True,
                        "pending_task_context": pending_task_context,
                    },
                }
            }
        }
        return state

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

# --> this is the entry point of the checkpointer <--
    async def run(self, state: GraphState) -> GraphState:
        memory = state.get("memory_context") or {}

        pending_task_context = memory.get("pending_task_context")
        recent_messages = memory.get("recent_messages", [])
        latest_user_message = memory.get("user_message") or state.get("query", "")
        summary_memory = memory.get("summary_memory", "")
        has_pending_task_context = bool(pending_task_context)
        pending_tool_context = self._find_pending_tool_context(pending_task_context)

        if not pending_task_context and not recent_messages:
            state["resume_context"] = None
            state["workflow_status"] = "RUNNING"

            state.setdefault("execution_logs", []).append(
                {
                    "node": "CheckpointResumeNode",
                    "status": "NO_PENDING_CONTEXT",
                }
            )

            return state

        if pending_task_context is None:
            pending_task_context = {}

        deterministic_payload = self._deterministic_missing_input_payload(
            latest_user_message=latest_user_message,
            pending_tool_context=pending_tool_context,
        )

        if pending_tool_context and pending_tool_context.get("confirmation_required"):
            confirmation_decision = await self._classify_confirmation_response(
                latest_user_message=latest_user_message,
                pending_task_context=pending_task_context,
                recent_messages=recent_messages,
            )

            if (
                confirmation_decision.is_confirmation_response
                and not confirmation_decision.needs_user_input
                and confirmation_decision.confirmed
            ):
                return self._apply_tool_resume_plan(
                    state=state,
                    pending_tool_context=pending_tool_context,
                    resolved_payload={},
                    reason=confirmation_decision.reason,
                    confirmed=True,
                )

            if (
                confirmation_decision.is_confirmation_response
                and not confirmation_decision.needs_user_input
                and not confirmation_decision.confirmed
            ):
                return self._cancel_pending_confirmation(
                    state=state,
                    pending_task_context=pending_task_context,
                )

            if confirmation_decision.needs_user_input:
                state["waiting_for_user_input"] = True
                state["workflow_status"] = "WAITING_FOR_USER"
                state["pending_human_input"] = {
                    "type": "CONFIRMATION",
                    "message": "Please confirm whether you want me to proceed.",
                    "payload": pending_task_context,
                }
                return state

        if deterministic_payload and pending_tool_context:
            return self._apply_tool_resume_plan(
                state=state,
                pending_tool_context=pending_tool_context,
                resolved_payload=deterministic_payload,
                reason="User provided the missing field for the pending tool call.",
            )

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
                "available_tools": json.dumps(
                    self._available_business_tools(),
                    default=str,
                    ensure_ascii=False,
                ),
            }
        )

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
            resumed_tool_context = self._build_pending_tool_context_from_decision(
                decision=decision,
                pending_tool_context=pending_tool_context,
                memory=memory,
            )

            if resumed_tool_context:
                confirmed = False

                if self._is_confirmation_resume_type(decision.resume_type):
                    confirmation_decision = await self._classify_confirmation_response(
                        latest_user_message=latest_user_message,
                        pending_task_context=pending_task_context,
                        recent_messages=recent_messages,
                    )
                    confirmed = (
                        confirmation_decision.is_confirmation_response
                        and confirmation_decision.confirmed
                        and not confirmation_decision.needs_user_input
                    )

                return self._apply_tool_resume_plan(
                    state=state,
                    pending_tool_context=resumed_tool_context,
                    resolved_payload=decision.resolved_payload or {},
                    reason=decision.reason,
                    confirmed=confirmed,
                )

            if decision.resume_type == "selection" and selected_data:
                return self._apply_resolved_payload_result(
                    state=state,
                    task_id=decision.task_id or "resolved_selection",
                    selected_data=selected_data,
                )

            return state

        if not has_pending_task_context:
            state["resume_context"] = {
                "can_resume": False,
                "resume_type": decision.resume_type,
                "reason": decision.reason,
                "pending_task_context": pending_task_context,
            }
            state["workflow_status"] = "RUNNING"
            state.setdefault("execution_logs", []).append(
                {
                    "node": "CheckpointResumeNode",
                    "status": "NO_RESUMABLE_RECENT_CONTEXT",
                    "reason": decision.reason,
                }
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
