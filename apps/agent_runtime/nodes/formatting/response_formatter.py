import json
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from apps.agent_runtime.agents.prompts.formatting.response_message_prompt import (
    response_message_prompt,
)
from apps.agent_runtime.agents.schemas.formatting.response_message import (
    ResponseMessage,
)
from apps.agent_runtime.llms.openai.openai_client import openai_llm
from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.runtime.progress_events import emit_progress


class SummaryMemoryUpdate(BaseModel):
    summary_memory: str = Field(
        description="Compact persistent assistant memory summary."
    )


class ResponseFormatter:

    def __init__(self):
        structured_llm = openai_llm.with_structured_output(
            ResponseMessage,
            method="function_calling",
        )
        self.message_chain = response_message_prompt | structured_llm

        summary_llm = openai_llm.with_structured_output(
            SummaryMemoryUpdate,
            method="function_calling",
        )
        self.summary_chain = self._summary_prompt() | summary_llm

    def _summary_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You update compact persistent memory for an enterprise assistant.

Rules:
1. Preserve useful long-term context from the existing summary.
2. Add important facts from recent messages, the latest user message, and the assistant response.
3. Keep unresolved follow-up questions, pending confirmations, selected entities, user preferences, and active workflow context.
4. Do not store secrets, auth tokens, raw IDs unless needed to continue a pending workflow, or unnecessary transient progress details.
5. Keep the summary concise and factual. Maximum 1200 characters.
6. If there is nothing useful to remember, return the existing summary or an empty string.
Return structured output only.
                    """,
                ),
                (
                    "human",
                    """
Existing Summary Memory:
{summary_memory}

Recent Messages:
{recent_messages}

Latest User Message:
{latest_user_message}

Assistant Response:
{assistant_response}

Event Type:
{event_type}

Workflow Status:
{workflow_status}
                    """,
                ),
            ]
        )

    async def run(self, state: GraphState) -> GraphState:
        emit_progress(
            state,
            "analyzing",
            "Preparing the response...",
            {
                "stage": "response_formatting",
            },
        )
        normalized = self._normalize_all_results(state)
        event = await self._build_event(state, normalized)

        state["final_response"] = event
        return state

    async def _build_event(
        self, state: GraphState, normalized: Dict[str, Any]
    ) -> Dict[str, Any]:

        workflow_status = state.get("workflow_status")

        if workflow_status == "FAILED":
            return await self._event(
                state,
                normalized,
                "run_failed",
                "Unable to complete the request.",
                self._pure_results_payload(normalized),
            )

        if workflow_status == "PERMISSION_DENIED":
            return await self._event(
                state,
                normalized,
                "permission_denied",
                "You do not have permission to perform this action.",
                self._pure_results_payload(normalized),
            )

        waiting_event = await self._detect_waiting_event(state, normalized)

        if waiting_event:
            return waiting_event

        return await self._event(
            state,
            normalized,
            "final_message",
            self._make_success_message(state, normalized),
            self._pure_results_payload(normalized),
        )

    def _pure_results_payload(self, normalized: Dict[str, Any]) -> Dict[str, Any]:

        if len(normalized) == 1:
            result = next(iter(normalized.values()))
            return self._pure_single_payload(result)

        output = {}

        for task_id, result in normalized.items():
            output[task_id] = self._pure_single_payload(result)

        return output

    def _pure_single_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:

        data = result.get("data")

        if isinstance(data, dict):
            return data

        return {"value": data}

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
                normalized_item = dict(item)
                normalized_item["id"] = item.get("id")
                normalized_item["label"] = (
                    item.get("label")
                    or item.get("name")
                    or item.get("title")
                    or item.get("email")
                    or item.get("id")
                )
                normalized_item["type"] = item.get("type")
                normalized_item["confidence"] = item.get("confidence")
                normalized.append(normalized_item)
            else:
                normalized.append(
                    {
                        "id": None,
                        "label": str(item),
                        "type": None,
                        "confidence": None,
                    }
                )

        return normalized

    def _infer_fields(self, items: Any) -> List[str]:

        if isinstance(items, list) and items and isinstance(items[0], dict):
            return list(items[0].keys())

        if isinstance(items, dict):
            return list(items.keys())

        return []

    async def _detect_waiting_event(
        self, state: GraphState, normalized: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:

        if state.get("pending_human_input"):
            human_input = state["pending_human_input"]

            return await self._event(
                state,
                normalized,
                self._waiting_event_type(human_input),
                human_input.get("message", "I need more information to continue."),
                self._clean_waiting_payload(human_input),
            )

        for task_id, result in normalized.items():
            status = result.get("status")
            ui = result.get("ui", {})

            if status == "requires_confirmation":
                return await self._event(
                    state,
                    normalized,
                    "confirmation_required",
                    result.get("message") or "Please confirm to continue.",
                    {
                        "task_id": task_id,
                        "waitingFor": "confirmation_required",
                        "confirmationRequired": True,
                        "data": result.get("data", {}),
                    },
                )

            if status == "requires_input":
                return await self._event(
                    state,
                    normalized,
                    "follow_up_question",
                    result.get("message") or "I need more information to continue.",
                    {
                        "task_id": task_id,
                        "data": result.get("data", {}),
                    },
                )

            if ui.get("type") == "options":
                candidates = ui.get("items", [])

                return await self._event(
                    state,
                    normalized,
                    "follow_up_question",
                    self._options_question(ui.get("title", "results"), candidates),
                    {
                        "task_id": task_id,
                        "candidates": candidates,
                    },
                )

        return None

    def _options_question(self, title: str, candidates: List[Dict[str, Any]]) -> str:
        readable_title = str(title or "results").replace("_", " ")
        labels = []

        for index, candidate in enumerate(candidates[:8], start=1):
            if not isinstance(candidate, dict):
                continue

            label = (
                candidate.get("label")
                or candidate.get("name")
                or candidate.get("title")
                or candidate.get("email")
                or candidate.get("id")
            )

            if label:
                labels.append(f"{index}. {label}")

        if labels:
            return (
                f"I found multiple matching {readable_title}. "
                f"Please reply with the number or exact name: {'; '.join(labels)}"
            )

        return f"I found multiple matching {readable_title}. Please reply with the number or exact name."

    def _clean_waiting_payload(self, human_input: Dict[str, Any]) -> Dict[str, Any]:
        data = human_input.get("data")
        extracted_data = self._extract_tool_context(data)

        if extracted_data:
            data = extracted_data
        elif not isinstance(data, dict):
            data = self._extract_tool_context(human_input)

        payload = {
            "type": human_input.get("type") or "follow_up_question",
            "waitingFor": self._waiting_event_type(human_input),
            "confirmationRequired": self._waiting_event_type(human_input)
            == "confirmation_required",
        }

        task_id = human_input.get("task_id") or data.get("task_id")

        if task_id:
            payload["task_id"] = task_id

        if data:
            payload["data"] = data

        return payload

    def _extract_tool_context(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            data = value.get("data")

            if isinstance(data, dict) and (
                data.get("tool_name")
                or data.get("missing_fields")
                or data.get("provided_arguments")
            ):
                return {
                    key: data[key]
                    for key in (
                        "tool_name",
                        "missing_fields",
                        "provided_arguments",
                        "task_id",
                    )
                    if key in data
                }

            if (
                value.get("tool_name")
                or value.get("missing_fields")
                or value.get("provided_arguments")
            ):
                return {
                    key: value[key]
                    for key in (
                        "tool_name",
                        "missing_fields",
                        "provided_arguments",
                        "task_id",
                    )
                    if key in value
                }

            for key in ("payload", "human_input"):
                child = value.get(key)

                if isinstance(child, dict):
                    found = self._extract_tool_context(child)

                    if found:
                        return found

        return {}

    def _waiting_event_type(self, human_input: Dict[str, Any]) -> str:

        input_type = str(human_input.get("type") or "").upper()

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
            data = result.get("data")

            if result.get("message"):
                return result["message"]

            data_message = self._message_from_data(data, ui)

            if data_message:
                return data_message

            if ui.get("type") == "detail":
                return "Here are the details I found."

            if ui.get("type") in ["list", "table"]:
                return "Here are the results I found."

        completed = len(
            [
                result
                for result in normalized.values()
                if result.get("status") == "success"
            ]
        )

        if completed:
            return f"Completed {completed} task{'s' if completed != 1 else ''} successfully."

        return "I completed the request."

    def _message_from_data(self, data: Any, ui: Dict[str, Any]) -> Optional[str]:

        if isinstance(data, dict):
            list_key = self._find_list_key(data)

            if list_key and isinstance(data.get(list_key), list):
                items = data[list_key]
                return self._message_from_items(items, list_key)

            summary = self._summarize_dict(data)

            if summary:
                return f"I found {summary}."

        if isinstance(data, list):
            return self._message_from_items(
                data,
                ui.get("title") or "results",
            )

        if data not in (None, ""):
            return str(data)

        return None

    def _message_from_items(self, items: List[Any], title: str) -> str:

        count = len(items)
        readable_title = str(title or "results").replace("_", " ")

        if count == 0:
            return f"I did not find any {readable_title}."

        labels = []

        for item in items[:3]:
            if isinstance(item, dict):
                label = (
                    item.get("label")
                    or item.get("name")
                    or item.get("title")
                    or item.get("email")
                    or item.get("id")
                )
                if label:
                    labels.append(str(label))
            elif item not in (None, ""):
                labels.append(str(item))

        if labels:
            return (
                f"I found {count} {readable_title}: "
                f"{', '.join(labels)}"
                f"{'...' if count > len(labels) else ''}."
            )

        return f"I found {count} {readable_title}."

    def _summarize_dict(self, data: Dict[str, Any]) -> str:

        label = (
            data.get("label")
            or data.get("name")
            or data.get("title")
            or data.get("email")
            or data.get("id")
        )

        details = []

        for key, value in data.items():
            if key in {"label", "name", "title", "id"}:
                continue

            if isinstance(value, (dict, list)) or value in (None, ""):
                continue

            details.append(f"{str(key).replace('_', ' ')} {value}")

            if len(details) == 3:
                break

        if label and details:
            return f"{label} with {', '.join(details)}"

        if label:
            return str(label)

        if details:
            return ", ".join(details)

        return ""

    async def _event(
        self,
        state: GraphState,
        normalized: Dict[str, Any],
        event_type: str,
        message: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        payload = dict(payload or {})
        payload_message = self._extract_payload_message(payload)
        base_message = payload_message or message

        dynamic_message = payload_message or await self._generate_message(
            state=state,
            normalized=normalized,
            event_type=event_type,
            base_message=base_message,
            payload=payload,
        )
        final_message = dynamic_message or base_message
        summary_memory = await self._build_summary_memory(
            state=state,
            event_type=event_type,
            assistant_response=final_message,
        )

        if summary_memory:
            payload["summary_memory"] = summary_memory

        payload["message"] = final_message

        return {
            "event_type": event_type,
            "message": final_message,
            "payload_json": json.dumps(payload, default=str),
            "summary_memory": summary_memory,
        }

    async def _build_summary_memory(
        self,
        state: GraphState,
        event_type: str,
        assistant_response: str,
    ) -> str:

        memory_context = state.get("memory_context") or {}
        existing_summary = str(memory_context.get("summary_memory") or "").strip()
        recent_messages = memory_context.get("recent_messages") or []
        latest_user_message = (
            memory_context.get("user_message")
            or state.get("query")
            or ""
        )

        try:
            response = await self.summary_chain.ainvoke(
                {
                    "summary_memory": existing_summary,
                    "recent_messages": self._safe_json(
                        recent_messages,
                        max_length=5000,
                    ),
                    "latest_user_message": str(latest_user_message or ""),
                    "assistant_response": str(assistant_response or ""),
                    "event_type": event_type,
                    "workflow_status": state.get("workflow_status", ""),
                }
            )

            summary_memory = str(response.summary_memory or "").strip()

            if summary_memory:
                return summary_memory[:1200]

        except Exception as exc:
            print(f"Summary memory generation failed: {exc}")

        return self._fallback_summary_memory(
            existing_summary=existing_summary,
            recent_messages=recent_messages,
            latest_user_message=str(latest_user_message or ""),
            assistant_response=str(assistant_response or ""),
        )

    def _fallback_summary_memory(
        self,
        existing_summary: str,
        recent_messages: Any,
        latest_user_message: str,
        assistant_response: str,
    ) -> str:

        parts = []

        if existing_summary:
            parts.append(existing_summary)

        compact_messages = self._compact_recent_messages(recent_messages)

        if compact_messages:
            parts.append(f"Recent conversation: {compact_messages}")

        latest_user_message = latest_user_message.strip()
        assistant_response = assistant_response.strip()

        if latest_user_message:
            parts.append(f"Latest user message: {latest_user_message}")

        if assistant_response:
            parts.append(f"Latest assistant response: {assistant_response}")

        return " ".join(parts).strip()[:1200]

    def _compact_recent_messages(self, recent_messages: Any) -> str:

        if not isinstance(recent_messages, list):
            return ""

        compact = []

        for item in recent_messages[-6:]:
            if not isinstance(item, dict):
                continue

            sender = str(item.get("senderType") or "unknown").strip()
            message = str(item.get("message") or "").strip()

            if not message:
                continue

            compact.append(f"{sender}: {message}")

        return " | ".join(compact)

    def _extract_payload_message(self, payload: Dict[str, Any]) -> Optional[str]:

        message = payload.get("message")

        if isinstance(message, str) and message.strip():
            return message.strip()

        data = payload.get("data")

        if isinstance(data, dict):
            message = data.get("message")

            if isinstance(message, str) and message.strip():
                return message.strip()

        return None

    async def _generate_message(
        self,
        state: GraphState,
        normalized: Dict[str, Any],
        event_type: str,
        base_message: str,
        payload: Dict[str, Any],
    ) -> str:

        try:
            response = await self.message_chain.ainvoke(
                {
                    "query": state.get("query", ""),
                    "workflow_status": state.get("workflow_status", ""),
                    "event_type": event_type,
                    "base_message": base_message,
                    "payload": self._safe_json(payload),
                    "normalized_results": self._safe_json(normalized),
                }
            )

            print(
                "this is the response form formatter messsafe in final response ",
                response,
            )
            return response.message.strip()
        except Exception as exc:
            print(f"Response message generation failed: {exc}")
            return base_message

    def _safe_json(self, value: Any, max_length: int = 6000) -> str:

        try:
            serialized = json.dumps(value, default=str, ensure_ascii=False)
        except Exception:
            serialized = str(value)

        if len(serialized) <= max_length:
            return serialized

        return serialized[:max_length] + "...[truncated]"
