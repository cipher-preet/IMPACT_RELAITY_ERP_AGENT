import json
from typing import Any, Dict, List, Optional

from apps.agent_runtime.state.graph_state import GraphState


class ResponseFormatter:

    async def run(self, state: GraphState) -> GraphState:
        normalized = self._normalize_all_results(state)
        event = self._build_event(state, normalized)

        state["final_response"] = event
        return state

    def _build_event(
        self, state: GraphState, normalized: Dict[str, Any]
    ) -> Dict[str, Any]:

        workflow_status = state.get("workflow_status")

        if workflow_status == "FAILED":
            return self._event(
                "run_failed",
                "Unable to complete the request.",
                {
                    "success": False,
                    "workflow_id": state.get("workflow_id"),
                    "results": normalized,
                },
            )

        if workflow_status == "PERMISSION_DENIED":
            return self._event(
                "permission_denied",
                "You do not have permission to perform this action.",
                {
                    "success": False,
                    "workflow_id": state.get("workflow_id"),
                    "results": normalized,
                },
            )

        waiting_event = self._detect_waiting_event(state, normalized)

        if waiting_event:
            return waiting_event

        return self._event(
            "final_message",
            self._make_success_message(state, normalized),
            {
                "success": True,
                "workflow_id": state.get("workflow_id"),
                "status": "COMPLETED",
                "results": normalized,
            },
        )

    def _normalize_all_results(self, state: GraphState) -> Dict[str, Any]:

        output = {}

        for task_id, raw_result in state.get("task_results", {}).items():
            output[task_id] = self._normalize_single_result(raw_result)

        return output

    def _normalize_single_result(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:

        if not isinstance(raw_result, dict):
            return {
                "status": "failed",
                "message": "Task returned an invalid result.",
                "data": {},
                "ui": self._infer_ui({}),
            }

        if raw_result.get("error"):
            return {
                "status": "failed",
                "message": raw_result.get("error"),
                "data": {},
                "ui": self._infer_ui({}),
            }

        result_data = raw_result.get("result") or {}

        if not isinstance(result_data, dict):
            return {
                "status": "failed",
                "message": "Task returned an invalid result.",
                "data": {},
                "ui": self._infer_ui({}),
            }

        structured = result_data.get("structuredContent") or {}

        if not isinstance(structured, dict):
            structured = {}

        status = structured.get("status", "success")
        data = structured.get("data", {})
        message = structured.get("message")

        ui = self._infer_ui(data)

        return {
            "status": status,
            "message": message,
            "data": data,
            "ui": ui,
        }

    def _infer_ui(self, data: Any) -> Dict[str, Any]:

        if isinstance(data, dict):
            list_key = self._find_list_key(data)

            if list_key:
                items = data[list_key]

                return {
                    "type": "options" if len(items) > 1 else "detail",
                    "title": list_key,
                    "items": self._normalize_items(items),
                    "fields": self._infer_fields(items),
                    "actions": [],
                }

            return {
                "type": "detail",
                "title": "Details",
                "items": [data],
                "fields": list(data.keys()),
                "actions": [],
            }

        if isinstance(data, list):
            return {
                "type": "list",
                "title": "Results",
                "items": self._normalize_items(data),
                "fields": self._infer_fields(data),
                "actions": [],
            }

        return {
            "type": "text",
            "title": "Result",
            "items": [{"value": data}],
            "fields": ["value"],
            "actions": [],
        }

    def _find_list_key(self, data: Dict[str, Any]) -> Optional[str]:

        for key, value in data.items():
            if isinstance(value, list):
                return key

        return None

    def _normalize_items(self, items: List[Any]) -> List[Dict[str, Any]]:

        normalized = []

        for item in items:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "id": item.get("id"),
                        "label": (
                            item.get("label")
                            or item.get("name")
                            or item.get("title")
                            or item.get("email")
                            or item.get("id")
                        ),
                        "type": item.get("type"),
                        "confidence": item.get("confidence"),
                        "raw": item,
                    }
                )
            else:
                normalized.append(
                    {
                        "id": None,
                        "label": str(item),
                        "type": None,
                        "confidence": None,
                        "raw": item,
                    }
                )

        return normalized

    def _infer_fields(self, items: Any) -> List[str]:

        if isinstance(items, list) and items and isinstance(items[0], dict):
            return list(items[0].keys())

        if isinstance(items, dict):
            return list(items.keys())

        return []

    def _detect_waiting_event(
        self, state: GraphState, normalized: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:

        if state.get("pending_human_input"):
            human_input = state["pending_human_input"]

            return self._event(
                self._waiting_event_type(human_input),
                human_input.get("message", "I need more information to continue."),
                human_input,
            )

        for task_id, result in normalized.items():
            status = result.get("status")
            ui = result.get("ui", {})

            if status == "requires_confirmation":
                return self._event(
                    "confirmation_required",
                    result.get("message") or "Please confirm to continue.",
                    {
                        "task_id": task_id,
                        "ui": ui,
                    },
                )

            if status == "requires_input":
                return self._event(
                    "follow_up_question",
                    result.get("message") or "I need more information to continue.",
                    {
                        "task_id": task_id,
                        "ui": ui,
                    },
                )

            if ui.get("type") == "options":
                return self._event(
                    "follow_up_question",
                    f"I found multiple matching {ui.get('title', 'results')}. Which one do you mean?",
                    {
                        "task_id": task_id,
                        "candidates": ui.get("items", []),
                        "ui": ui,
                    },
                )

        return None

    def _waiting_event_type(self, human_input: Dict[str, Any]) -> str:

        input_type = human_input.get("type")

        if input_type in ["CLARIFICATION", "OPTION_SELECTION", "FOLLOW_UP_QUESTION"]:
            return "follow_up_question"

        if input_type in ["APPROVAL", "CONFIRMATION", "CONFIRMATION_REQUIRED"]:
            return "confirmation_required"

        return "waiting_for_user"

    def _make_success_message(
        self, state: GraphState, normalized: Dict[str, Any]
    ) -> str:

        if len(normalized) == 1:
            result = next(iter(normalized.values()))
            ui = result.get("ui", {})

            if result.get("message"):
                return result["message"]

            if ui.get("type") == "detail":
                return "Here are the details I found."

            if ui.get("type") in ["list", "table"]:
                return "Here are the results I found."

        return "Request completed successfully."

    def _event(
        self, event_type: str, message: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:

        return {
            "event_type": event_type,
            "message": message,
            "payload_json": json.dumps(payload, default=str),
        }
