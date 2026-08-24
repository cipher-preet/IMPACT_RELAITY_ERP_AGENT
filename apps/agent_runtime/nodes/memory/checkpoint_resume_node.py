import json
import re
from typing import Any, Dict, Optional

from apps.agent_runtime.llms.openai.openai_client import openai_planning_llm


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
from apps.agent_runtime.runtime.progress_events import emit_progress
from apps.agent_runtime.tools.registry.tool_registry import tool_registry


class CheckpointResumeNode:

    def __init__(self):

        structured_llm = openai_planning_llm.with_structured_output(
            CheckpointResumeDecision,
            method="function_calling",
        )
        self.chain = checkpoint_resume_prompt | structured_llm
        confirmation_llm = openai_planning_llm.with_structured_output(
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

    def _is_executable_tool_name(self, tool_name: str) -> bool:
        if not tool_name:
            return False

        if str(tool_name).startswith("assistant."):
            return False

        return tool_registry.exists(tool_name)

    def _context_key(self, key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(key or "").lower())

    def _context_tokens(self, value: str) -> list:
        ignored_tokens = {
            "add",
            "call",
            "create",
            "delete",
            "detail",
            "details",
            "find",
            "get",
            "list",
            "remove",
            "search",
            "set",
            "tool",
            "tools",
            "update",
        }
        tokens = re.split(r"[^a-zA-Z0-9]+", str(value or ""))

        return [
            token.lower()
            for token in tokens
            if token and token.lower() not in ignored_tokens
        ]

    def _context_key_candidates(
        self,
        field_name: str,
        context_tokens: list = None,
    ) -> list:
        normalized = self._context_key(field_name)
        candidates = [normalized]

        if normalized.endswith("uuid"):
            without_uuid = normalized[:-4]
            candidates.append(without_uuid)

            if without_uuid and not without_uuid.endswith("id"):
                candidates.append(f"{without_uuid}id")

        if normalized in {"id", "uuid"}:
            for token in context_tokens or []:
                token_key = self._context_key(token)

                if token_key:
                    candidates.append(f"{token_key}id")

        return list(dict.fromkeys(candidate for candidate in candidates if candidate))

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

    def _is_positive_or_negative_reply(self, message: str) -> bool:
        normalized = str(message or "").strip().lower()

        return normalized in {
            "yes",
            "y",
            "yeah",
            "yep",
            "ok",
            "okay",
            "sure",
            "confirm",
            "confirmed",
            "approve",
            "approved",
            "proceed",
            "continue",
            "no",
            "n",
            "nope",
            "cancel",
            "stop",
            "don't",
            "do not",
        }

    def _pending_missing_fields(
        self,
        pending_tool_context: Optional[Dict[str, Any]],
    ) -> list:
        if not pending_tool_context:
            return []

        return [
            str(field)
            for field in pending_tool_context.get("missing_fields") or []
            if str(field or "").strip()
        ]

    def _mentions_missing_field(
        self,
        message: str,
        pending_tool_context: Optional[Dict[str, Any]],
    ) -> bool:
        normalized_message = str(message or "").lower()

        for field_name in self._pending_missing_fields(pending_tool_context):
            readable = str(field_name).replace("_", " ").replace(".", " ").lower()
            compact = self._context_key(field_name)

            if readable and readable in normalized_message:
                return True

            if compact and compact in self._context_key(normalized_message):
                return True

        return False

    def _looks_like_new_request(
        self,
        message: str,
        pending_tool_context: Optional[Dict[str, Any]],
    ) -> bool:
        normalized = " ".join(str(message or "").strip().lower().split())

        if not normalized:
            return False

        if self._is_positive_or_negative_reply(normalized):
            return False

        if self._mentions_missing_field(normalized, pending_tool_context):
            return False

        words = normalized.rstrip("?").split()

        if len(words) <= 3 and "?" not in normalized:
            return False

        first_word = words[0] if words else ""
        first_two = " ".join(words[:2])

        request_starters = {
            "what",
            "who",
            "when",
            "where",
            "why",
            "how",
            "list",
            "show",
            "get",
            "find",
            "search",
            "create",
            "add",
            "update",
            "delete",
            "remove",
            "send",
            "call",
            "schedule",
            "book",
            "tell",
            "give",
            "can",
            "could",
            "would",
            "do",
            "does",
            "is",
            "are",
        }

        polite_starters = {
            "please list",
            "please show",
            "please get",
            "please find",
            "please search",
            "please create",
            "please add",
            "please update",
            "please delete",
            "please send",
        }

        return (
            "?" in normalized
            or first_word in request_starters
            or first_two in polite_starters
        )

    def _ignore_pending_context(
        self,
        state: GraphState,
        reason: str,
    ) -> GraphState:
        self._clear_pending_memory_context(state)
        state["resume_context"] = {
            "can_resume": False,
            "resume_type": "ignored_stale_context",
            "reason": reason,
            "pending_task_context": None,
        }
        state["workflow_status"] = "RUNNING"
        state["waiting_for_user_input"] = False
        state["pending_human_input"] = None
        state.setdefault("execution_logs", []).append(
            {
                "node": "CheckpointResumeNode",
                "status": "IGNORED_STALE_PENDING_CONTEXT",
                "reason": reason,
            }
        )

        return state

    def _clear_pending_memory_context(self, state: GraphState) -> None:
        memory_context = dict(state.get("memory_context") or {})
        memory_context["pending_task_context"] = None
        state["memory_context"] = memory_context

    def _extract_candidates(self, value: Any) -> list:
        if isinstance(value, dict):
            for key in (
                "candidates",
                "options",
                "items",
                "results",
                "boards",
                "records",
                "data",
            ):
                child = value.get(key)

                if isinstance(child, list) and child:
                    dict_items = [item for item in child if isinstance(item, dict)]

                    if dict_items:
                        return dict_items

            for child in value.values():
                found = self._extract_candidates(child)

                if found:
                    return found

        if isinstance(value, list):
            dict_items = [item for item in value if isinstance(item, dict)]

            if dict_items:
                return dict_items

            for child in value:
                found = self._extract_candidates(child)

                if found:
                    return found

        return []

    def _candidate_data(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        metadata = candidate.get("metadata")

        if isinstance(metadata, dict):
            data = dict(metadata)
        else:
            data = dict(candidate)

        for field in ("id", "type", "label", "name", "title", "email", "confidence"):
            if field in candidate and field not in data:
                data[field] = candidate[field]

        return data

    def _candidate_values(self, candidate: Dict[str, Any]) -> list:
        data = self._candidate_data(candidate)
        values = []

        for key in ("id", "label", "name", "title", "email", "value"):
            value = data.get(key)

            if value not in (None, ""):
                values.append(str(value))

        return values

    def _selected_candidate_from_payload(self, candidates: list) -> Optional[Dict[str, Any]]:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            if candidate.get("selected") is True or candidate.get("isSelected") is True:
                return self._candidate_data(candidate)

            metadata = candidate.get("metadata")

            if isinstance(metadata, dict) and (
                metadata.get("selected") is True or metadata.get("isSelected") is True
            ):
                return self._candidate_data(candidate)

        return None

    def _selected_candidate_from_context(self, value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, dict):
            for key in (
                "selected_candidate",
                "selectedCandidate",
                "chosen_candidate",
                "chosenCandidate",
                "current_candidate",
                "currentCandidate",
            ):
                candidate = value.get(key)

                if isinstance(candidate, dict):
                    return self._candidate_data(candidate)

            for child in value.values():
                found = self._selected_candidate_from_context(child)

                if found:
                    return found

        if isinstance(value, list):
            for child in value:
                found = self._selected_candidate_from_context(child)

                if found:
                    return found

        return None

    def _ordinal_selection_index(self, message: str) -> Optional[int]:
        normalized = " ".join(str(message or "").strip().lower().split())

        ordinal_words = {
            "first": 0,
            "1st": 0,
            "second": 1,
            "2nd": 1,
            "third": 2,
            "3rd": 2,
            "fourth": 3,
            "4th": 3,
            "fifth": 4,
            "5th": 4,
        }

        number_match = re.search(
            r"(?:^|\b)(?:option|choice|number|#)?\s*([1-9]\d*)(?:\b|$)",
            normalized,
        )

        if number_match:
            return int(number_match.group(1)) - 1

        for word, index in ordinal_words.items():
            if re.search(rf"\b{re.escape(word)}\b", normalized):
                return index

        return None

    def _is_vague_selection_reply(self, message: str) -> bool:
        normalized = " ".join(str(message or "").strip().lower().split())

        return normalized in {
            "this",
            "this one",
            "that",
            "that one",
            "same",
            "same one",
            "it",
            "yes this",
            "yes this one",
        }

    def _match_candidate_selection(
        self,
        latest_user_message: str,
        candidates: list,
    ) -> Optional[Dict[str, Any]]:
        selected = self._selected_candidate_from_payload(candidates)

        if selected:
            return selected

        index = self._ordinal_selection_index(latest_user_message)

        if index is not None and 0 <= index < len(candidates):
            return self._candidate_data(candidates[index])

        normalized_message = str(latest_user_message or "").strip().lower()

        if not normalized_message:
            return None

        exact_matches = []
        partial_matches = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            values = [
                str(value).strip().lower()
                for value in self._candidate_values(candidate)
                if str(value).strip()
            ]

            if normalized_message in values:
                exact_matches.append(candidate)
                continue

            if len(normalized_message) >= 3 and any(
                normalized_message in value for value in values
            ):
                partial_matches.append(candidate)

        matches = exact_matches or partial_matches

        if len(matches) == 1:
            return self._candidate_data(matches[0])

        return None

    def _candidate_labels(self, candidates: list) -> list:
        labels = []

        for index, candidate in enumerate(candidates[:8], start=1):
            values = self._candidate_values(candidate)
            label = values[0] if values else f"Option {index}"
            labels.append(f"{index}. {label}")

        return labels

    def _ask_for_candidate_selection(
        self,
        state: GraphState,
        candidates: list,
    ) -> GraphState:
        labels = self._candidate_labels(candidates)
        if labels:
            message = "Please reply with the number or exact name: " + "; ".join(labels)
        else:
            message = "Please reply with the number or exact name."

        state["resume_context"] = {
            "can_resume": False,
            "resume_type": "selection",
            "reason": "Candidate selection was ambiguous.",
        }
        state["waiting_for_user_input"] = True
        state["workflow_status"] = "WAITING_FOR_USER"
        state["pending_human_input"] = {
            "type": "OPTION_SELECTION",
            "message": message,
            "data": {
                "candidates": candidates,
                "selection_required": True,
            },
        }
        state.setdefault("execution_logs", []).append(
            {
                "node": "CheckpointResumeNode",
                "status": "WAITING_FOR_CANDIDATE_SELECTION",
            }
        )

        return state

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
        context_tokens = self._context_tokens(tool_name)

        for field_name in properties:
            value = None

            for candidate_key in self._context_key_candidates(
                field_name,
                context_tokens,
            ):
                if candidate_key in auth_values:
                    value = auth_values[candidate_key]
                    break

            if value not in (None, ""):
                arguments[field_name] = value

        return arguments

    def _auth_value_for_field(
        self,
        field_name: str,
        memory: Dict[str, Any],
        tool_name: str = "",
    ) -> Any:
        auth_values = {
            "agencyid": memory.get("agency_id"),
            "userid": memory.get("user_id"),
            "runid": memory.get("run_id"),
            "sessionid": memory.get("session_id"),
        }

        for candidate_key in self._context_key_candidates(
            field_name,
            self._context_tokens(tool_name),
        ):
            value = auth_values.get(candidate_key)

            if value not in (None, ""):
                return value

        return None

    def _has_argument_value(
        self,
        arguments: Dict[str, Any],
        field_name: str,
        tool_name: str = "",
    ) -> bool:
        field_keys = set(
            self._context_key_candidates(
                field_name,
                self._context_tokens(tool_name),
            )
        )

        for key, value in arguments.items():
            if value in (None, ""):
                continue

            if self._context_key(key) in field_keys:
                return True

        return False

    def _hydrate_pending_tool_context_from_auth(
        self,
        pending_tool_context: Optional[Dict[str, Any]],
        memory: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not pending_tool_context:
            return pending_tool_context

        tool_name = pending_tool_context.get("tool_name")

        if not tool_name or not tool_registry.exists(tool_name):
            return pending_tool_context

        hydrated = dict(pending_tool_context)
        provided_arguments = dict(hydrated.get("provided_arguments") or {})
        provided_arguments.update(self._auth_arguments_for_tool(tool_name, memory))

        remaining_missing = []

        for field_name in hydrated.get("missing_fields") or []:
            if self._has_argument_value(provided_arguments, field_name, tool_name):
                continue

            auth_value = self._auth_value_for_field(field_name, memory, tool_name)

            if auth_value not in (None, ""):
                provided_arguments[field_name] = auth_value
                continue

            remaining_missing.append(field_name)

        hydrated["provided_arguments"] = provided_arguments
        hydrated["missing_fields"] = remaining_missing

        return hydrated

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

    async def run(self, state: GraphState) -> GraphState:
        try:
            return await self._run(state)
        except Exception as exc:
            print(f"Checkpoint resume failed; starting fresh request: {exc}")
            self._clear_pending_memory_context(state)
            state["resume_context"] = None
            state["workflow_status"] = "RUNNING"
            state["waiting_for_user_input"] = False
            state["pending_human_input"] = None
            state.setdefault("execution_logs", []).append(
                {
                    "node": "CheckpointResumeNode",
                    "status": "CHECKPOINT_RESUME_FAILED_FRESH_START",
                    "error": str(exc),
                }
            )

            return state

# --> this is the entry point of the checkpointer <--
    async def _run(self, state: GraphState) -> GraphState:
        memory = state.get("memory_context") or {}

        pending_task_context = memory.get("pending_task_context")
        recent_messages = memory.get("recent_messages", [])
        latest_user_message = memory.get("user_message") or state.get("query", "")
        summary_memory = memory.get("summary_memory", "")
        has_pending_task_context = bool(pending_task_context)
        pending_tool_context = self._find_pending_tool_context(pending_task_context)

        if pending_tool_context and not self._is_executable_tool_name(
            pending_tool_context.get("tool_name")
        ):
            pending_tool_context = None

        pending_tool_context = self._hydrate_pending_tool_context_from_auth(
            pending_tool_context,
            memory,
        )

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

        pending_candidates = self._extract_candidates(pending_task_context)

        if pending_candidates:
            if self._looks_like_new_request(latest_user_message, pending_tool_context):
                return self._ignore_pending_context(
                    state,
                    "Latest user message looks like a new request, not a candidate selection.",
                )

            selected_candidate = self._selected_candidate_from_context(
                pending_task_context
            ) or self._match_candidate_selection(
                latest_user_message,
                pending_candidates,
            )

            if selected_candidate:
                return self._apply_resolved_payload_result(
                    state=state,
                    task_id="resolved_selection",
                    selected_data=selected_candidate,
                )

            if self._is_vague_selection_reply(latest_user_message):
                return self._ask_for_candidate_selection(
                    state=state,
                    candidates=pending_candidates,
                )

        if has_pending_task_context and not pending_tool_context:
            return self._ignore_pending_context(
                state,
                "Pending context did not contain an executable tool call.",
            )

        if pending_tool_context and self._looks_like_new_request(
            latest_user_message,
            pending_tool_context,
        ):
            return self._ignore_pending_context(
                state,
                "Latest user message looks like a new request, not a reply to pending context.",
            )

        if (
            pending_tool_context
            and pending_tool_context.get("provided_arguments")
            and not pending_tool_context.get("missing_fields")
            and not pending_tool_context.get("confirmation_required")
        ):
            emit_progress(
                state,
                "analyzing",
                "Continuing with the existing context...",
                {
                    "stage": "missing_input_resolved_from_context",
                    "task_id": pending_tool_context.get("task_id"),
                },
            )

            return self._apply_tool_resume_plan(
                state=state,
                pending_tool_context=pending_tool_context,
                resolved_payload={},
                reason="Required context was already available.",
            )

        deterministic_payload = self._deterministic_missing_input_payload(
            latest_user_message=latest_user_message,
            pending_tool_context=pending_tool_context,
        )

        if pending_tool_context and pending_tool_context.get("confirmation_required"):
            emit_progress(
                state,
                "analyzing",
                "Checking the pending confirmation...",
                {
                    "stage": "confirmation_resume_check",
                    "task_id": pending_tool_context.get("task_id"),
                },
            )

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
                emit_progress(
                    state,
                    "analyzing",
                    "Continuing the confirmed task...",
                    {
                        "stage": "confirmation_confirmed",
                        "task_id": pending_tool_context.get("task_id"),
                    },
                )

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
                emit_progress(
                    state,
                    "analyzing",
                    "Cancelling the pending task as requested...",
                    {
                        "stage": "confirmation_cancelled",
                        "task_id": pending_tool_context.get("task_id"),
                    },
                )

                return self._cancel_pending_confirmation(
                    state=state,
                    pending_task_context=pending_task_context,
                )

            if confirmation_decision.needs_user_input:
                emit_progress(
                    state,
                    "analyzing",
                    "I need confirmation before continuing.",
                    {
                        "stage": "confirmation_needs_input",
                        "task_id": pending_tool_context.get("task_id"),
                    },
                )

                state["waiting_for_user_input"] = True
                state["workflow_status"] = "WAITING_FOR_USER"
                state["pending_human_input"] = {
                    "type": "CONFIRMATION",
                    "message": "Please confirm whether you want me to proceed.",
                    "data": pending_tool_context or pending_task_context,
                }
                return state

        if deterministic_payload and pending_tool_context:
            emit_progress(
                state,
                "analyzing",
                "Using your latest answer to continue the previous task...",
                {
                    "stage": "missing_input_resolved",
                    "task_id": pending_tool_context.get("task_id"),
                },
            )

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
            emit_progress(
                state,
                "analyzing",
                "Continuing the previous task...",
                {
                    "stage": "resume_detected",
                    "resume_type": decision.resume_type,
                    "task_id": decision.task_id,
                },
            )

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
            "data": pending_tool_context or pending_task_context,
        }

        emit_progress(
            state,
            "analyzing",
            "I need a little more information before continuing.",
            {
                "stage": "resume_needs_clarification",
                "resume_type": decision.resume_type,
            },
        )

        state.setdefault("execution_logs", []).append(
            {
                "node": "CheckpointResumeNode",
                "status": "WAITING_FOR_USER",
                "reason": decision.reason,
            }
        )

        return state
