from types import SimpleNamespace

from apps.agent_runtime.agents.executor.argument_generator import argument_generator
from apps.agent_runtime.agents.executor.entity_resolver import entity_resolver
from apps.agent_runtime.mcp.client.mcp_client import mcp_client
from apps.agent_runtime.nodes.execution.tool_selector import tool_selector
from apps.agent_runtime.tools.registry.tool_registry import tool_registry
from apps.agent_runtime.runtime.progress_events import emit_progress

class TaskExecutor:

    DUMMY_VALUES = {
        "dummy",
        "test",
        "sample",
        "example",
        "placeholder",
        "unknown",
        "n/a",
        "na",
        "none",
        "null",
        "string",
        "user@example.com",
        "example@example.com",
        "john doe",
        "jane doe",
        "123",
        "12345",
        "000",
    }

    BLOCKED_TOOL_NAMES = {
        "assistant.list_tools",
    }

    def _clean_text(self, value) -> str:
        return " ".join(str(value or "").replace("_", " ").split())

    def _task_summary(self, task: dict) -> str:
        description = self._clean_text(task.get("description"))

        if description:
            return description.rstrip(".")

        action = self._clean_text(task.get("action")).lower()
        module = self._clean_text(task.get("module")).lower()

        if action and module:
            return f"{action} in {module}"

        return action or module or "this action"

    def _preparation_message(self, task: dict) -> str:
        summary = self._task_summary(task)
        required_entities = task.get("required_entities") or []

        if required_entities:
            readable_entities = ", ".join(
                self._clean_text(entity).lower()
                for entity in required_entities[:3]
                if self._clean_text(entity)
            )

            if readable_entities:
                return f"I am checking the required {readable_entities} for {summary}."

        return f"I am preparing the details needed to {summary}."

    def _run_message(self, task: dict) -> str:
        return f"{self._task_summary(task).capitalize()}..."

    def _completed_message(self, task: dict) -> str:
        return f"{self._task_summary(task).capitalize()} completed."

    def _business_tools(self) -> list:
        return [
            tool
            for tool in tool_registry.get_all_tools()
            if not str(tool.get("name", "")).startswith("assistant.")
            and tool.get("name") not in self.BLOCKED_TOOL_NAMES
        ]

    def _is_blocked_tool(self, tool_name: str) -> bool:
        return (
            str(tool_name or "").startswith("assistant.")
            or tool_name in self.BLOCKED_TOOL_NAMES
        )

    def _is_confirmed_task(self, task: dict) -> bool:
        value = task.get("confirmed")

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {
                "true",
                "yes",
                "confirmed",
                "confirm",
                "approved",
                "approve",
                "proceed",
            }

        return False

    def _schema_properties(self, schema: dict) -> dict:
        if not isinstance(schema, dict):
            return {}

        properties = schema.get("properties")

        return properties if isinstance(properties, dict) else {}

    def _is_dummy_value(self, field_name: str, value) -> bool:
        if not isinstance(value, str):
            return False

        normalized_value = value.strip().lower()
        normalized_field = str(field_name or "").strip().lower()

        if not normalized_value:
            return True

        if normalized_value in self.DUMMY_VALUES:
            return True

        if normalized_field and normalized_value in {
            normalized_field,
            f"{normalized_field}_id",
            f"{{{normalized_field}}}",
            f"<{normalized_field}>",
        }:
            return True

        return any(token in normalized_value for token in ["dummy", "placeholder"])

    def _is_missing_value(self, field_name: str, value, schema: dict) -> bool:
        if value is None:
            return True

        if isinstance(value, str):
            return self._is_dummy_value(field_name, value)

        if isinstance(value, (list, dict)) and not value:
            return True

        if isinstance(schema, dict) and schema.get("type") == "array":
            min_items = schema.get("minItems")
            if isinstance(value, list) and isinstance(min_items, int):
                return len(value) < min_items

        return False

    def _missing_required_fields(
        self,
        arguments: dict,
        schema: dict,
        prefix: str = "",
    ) -> list:
        if not isinstance(schema, dict):
            return []

        properties = self._schema_properties(schema)
        required_fields = schema.get("required") or []
        missing_fields = []

        for field_name in required_fields:
            field_schema = properties.get(field_name, {})
            field_path = f"{prefix}.{field_name}" if prefix else str(field_name)

            if not isinstance(arguments, dict) or field_name not in arguments:
                missing_fields.append(field_path)
                continue

            value = arguments.get(field_name)

            if self._is_missing_value(field_name, value, field_schema):
                missing_fields.append(field_path)
                continue

            if isinstance(value, dict):
                missing_fields.extend(
                    self._missing_required_fields(value, field_schema, field_path)
                )

        return missing_fields

    def _sanitize_arguments(self, arguments: dict, schema: dict) -> dict:
        if not isinstance(arguments, dict):
            return {}

        properties = self._schema_properties(schema)

        if not properties:
            return dict(arguments)

        sanitized = {}

        for field_name, field_schema in properties.items():
            if field_name not in arguments:
                continue

            value = arguments[field_name]

            if self._is_missing_value(field_name, value, field_schema):
                continue

            if isinstance(value, dict):
                value = self._sanitize_arguments(value, field_schema)

            sanitized[field_name] = value

        return sanitized

    def _clarification_result(
        self,
        tool_name: str,
        missing_fields: list,
        arguments: dict,
    ) -> dict:
        readable_fields = [
            str(field).replace("_", " ").replace(".", " ") for field in missing_fields
        ]
        field_text = ", ".join(readable_fields)

        return {
            "result": {
                "structuredContent": {
                    "status": "requires_input",
                    "message": (
                        f"Please provide {field_text} so I can continue."
                        if field_text
                        else "Please provide the missing information so I can continue."
                    ),
                    "data": {
                        "tool_name": tool_name,
                        "missing_fields": missing_fields,
                        "provided_arguments": arguments,
                    },
                }
            }
        }

    def _with_execution_context(
        self,
        result: dict,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        if not isinstance(result, dict):
            return result

        result_data = result.get("result")

        if not isinstance(result_data, dict):
            return result

        structured = result_data.get("structuredContent")

        if not isinstance(structured, dict):
            return result

        status = str(structured.get("status") or "").lower()

        if status not in {"requires_input", "requires_confirmation"}:
            return result

        data = structured.get("data")

        if not isinstance(data, dict):
            data = {}
            structured["data"] = data

        data.setdefault("tool_name", tool_name)
        data.setdefault("provided_arguments", arguments)

        return result

    def _id_missing_fields(self, missing_fields: list) -> list:
        return [field for field in missing_fields if str(field).lower().endswith("id")]

    def _normalize_match_value(self, value) -> str:
        return str(value or "").strip().lower()

    def _candidate_label_values(self, candidate: dict) -> list:
        values = []

        for key in ("id", "label", "name", "title", "email"):
            value = candidate.get(key)

            if value not in (None, ""):
                values.append(value)

        metadata = candidate.get("metadata")

        if isinstance(metadata, dict):
            for key in ("id", "label", "name", "title", "email"):
                value = metadata.get(key)

                if value not in (None, ""):
                    values.append(value)

        return values

    def _iter_context_candidates(self, value):
        if isinstance(value, dict):
            if value.get("id"):
                yield value

            for child in value.values():
                yield from self._iter_context_candidates(child)

        if isinstance(value, list):
            for child in value:
                yield from self._iter_context_candidates(child)

    def _find_context_id(self, lookup_value: str, *contexts):
        lookup = self._normalize_match_value(lookup_value)

        if not lookup:
            return None

        for context in contexts:
            for candidate in self._iter_context_candidates(context):
                for value in self._candidate_label_values(candidate):
                    if self._normalize_match_value(value) == lookup:
                        return candidate.get("id") or (
                            candidate.get("metadata") or {}
                        ).get("id")

        return None

    def _extract_result_candidates(self, result: dict) -> list:
        result_data = result.get("result") if isinstance(result, dict) else {}
        structured = (
            result_data.get("structuredContent")
            if isinstance(result_data, dict)
            else {}
        )
        data = structured.get("data") if isinstance(structured, dict) else {}

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            candidates = []

            for value in data.values():
                if isinstance(value, list):
                    candidates.extend(value)

            return candidates

        return []

    def _match_candidates(self, candidates: list, lookup_value: str) -> list:
        lookup = self._normalize_match_value(lookup_value)
        matches = []
        partial_matches = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            values = [
                self._normalize_match_value(value)
                for value in self._candidate_label_values(candidate)
            ]

            if lookup in values:
                matches.append(candidate)
                continue

            if any(lookup and lookup in value for value in values):
                partial_matches.append(candidate)

        return matches or partial_matches

    async def _resolve_missing_ids(
        self,
        state: dict,
        task: dict,
        selected_tool_name: str,
        selected_tool_schema: dict,
        arguments: dict,
        missing_fields: list,
        auth_context: dict,
    ):
        id_missing_fields = self._id_missing_fields(missing_fields)

        if not id_missing_fields:
            return arguments, missing_fields, None

        plan = await entity_resolver.plan_resolution(
            query=state.get("query"),
            task=task,
            target_tool_name=selected_tool_name,
            target_tool_schema=selected_tool_schema,
            current_arguments=arguments,
            missing_fields=id_missing_fields,
            memory_context=state.get("memory_context", {}),
            auth_context=auth_context,
            available_tools=self._business_tools(),
        )

        if not plan.get("needs_resolution"):
            return arguments, missing_fields, None

        target_field = plan.get("target_field")
        lookup_value = plan.get("lookup_value")
        resolver_tool_name = plan.get("resolver_tool_name")

        if target_field not in missing_fields or not lookup_value:
            return arguments, missing_fields, None

        context_id = self._find_context_id(
            lookup_value,
            state.get("memory_context", {}),
            state.get("task_results", {}),
        )

        if context_id:
            arguments[target_field] = context_id
            return (
                arguments,
                [field for field in missing_fields if field != target_field],
                None,
            )

        if self._is_blocked_tool(resolver_tool_name):
            return arguments, missing_fields, None

        resolver_tool_info = tool_registry.get_tool(resolver_tool_name)

        if not resolver_tool_info:
            return arguments, missing_fields, None

        resolver_schema = resolver_tool_info.get("inputSchema") or {}
        resolver_arguments = self._sanitize_arguments(
            plan.get("resolver_arguments") or {},
            resolver_schema,
        )
        resolver_missing = self._missing_required_fields(
            resolver_arguments,
            resolver_schema,
        )

        if resolver_missing:
            return arguments, missing_fields, None

        resolver_result = await mcp_client.call_tool(
            tool_name=resolver_tool_name,
            arguments=resolver_arguments,
            run_id=auth_context.get("run_id"),
            agency_id=auth_context.get("agency_id"),
        )
        candidates = self._extract_result_candidates(resolver_result)
        matches = self._match_candidates(candidates, lookup_value)

        if len(matches) == 1:
            match_id = matches[0].get("id") or (matches[0].get("metadata") or {}).get(
                "id"
            )

            if match_id:
                arguments[target_field] = match_id
                return (
                    arguments,
                    [field for field in missing_fields if field != target_field],
                    None,
                )

        if len(matches) > 1:
            return (
                arguments,
                missing_fields,
                {
                    "result": {
                        "structuredContent": {
                            "status": "requires_input",
                            "message": "I found multiple matching records. Which one do you mean?",
                            "data": {
                                "tool_name": selected_tool_name,
                                "missing_fields": missing_fields,
                                "provided_arguments": arguments,
                                "candidates": matches,
                            },
                        }
                    }
                },
            )

        return arguments, missing_fields, None

    # --> This is Entry Point <--
    async def execute(self, task: dict, state):

        auth_context = state.get("auth_context", {})

        forced_tool_name = task.get("tool_name") or task.get("forced_tool_name")

        if self._is_blocked_tool(forced_tool_name):
            return self._clarification_result(
                tool_name="business_tool",
                missing_fields=[],
                arguments={},
            )

        if forced_tool_name:
            selected_tool = SimpleNamespace(name=forced_tool_name)
        else:
            selected_tool = await tool_selector.select(
                task=task,
                available_tools=self._business_tools(),
                memory_context=state.get("memory_context", {}),
            )

        if self._is_blocked_tool(selected_tool.name):
            return self._clarification_result(
                tool_name="business_tool",
                missing_fields=[],
                arguments={},
            )

        get_tool_info = tool_registry.get_tool(selected_tool.name)

        if not get_tool_info:
            return {
                "result": {
                    "structuredContent": {
                        "status": "failed",
                        "message": "The required action is not available.",
                        "data": {},
                    }
                }
            }

        if forced_tool_name and isinstance(task.get("arguments"), dict):
            generated_arguments = {
                "arguments": task.get("arguments") or {},
                "needs_clarification": False,
                "missing_fields": [],
            }
        else:
            emit_progress(
                state,
                "analyzing",
                self._preparation_message(task),
                {
                    "stage": "argument_generation",
                    "task_id": task.get("task_id"),
                },
            )
            generated_arguments = await argument_generator.generate_arguments(
                query=state.get("query"),
                tool_name=selected_tool.name,
                tool_schema=get_tool_info.get("inputSchema"),
                task=task,
                resolved_entities=state.get("resolved_entities", {}),
                task_results=state.get("task_results", {}),
                auth_context=auth_context,
                memory_context=state.get("memory_context", {}),
            )
        tool_schema = get_tool_info.get("inputSchema") or {}
        arguments = self._sanitize_arguments(
            generated_arguments.get("arguments", {}),
            tool_schema,
        )
        missing_fields = self._missing_required_fields(arguments, tool_schema)

        if missing_fields:
            arguments, missing_fields, resolution_result = (
                await self._resolve_missing_ids(
                    state=state,
                    task=task,
                    selected_tool_name=selected_tool.name,
                    selected_tool_schema=tool_schema,
                    arguments=arguments,
                    missing_fields=missing_fields,
                    auth_context=auth_context,
                )
            )

            if resolution_result:
                return resolution_result

        if generated_arguments.get("needs_clarification") or missing_fields:
            missing_fields = missing_fields or generated_arguments.get(
                "missing_fields",
                [],
            )
            return self._clarification_result(
                tool_name=selected_tool.name,
                missing_fields=missing_fields,
                arguments=arguments,
            )

        emit_progress(
            state,
            "tool_start",
            self._run_message(task),
            {
                "stage": "tool_call_started",
                "task_id": task.get("task_id"),
            },
        )

        result = await mcp_client.call_tool(
            tool_name=selected_tool.name,
            arguments=arguments,
            run_id=auth_context.get("run_id"),
            agency_id=auth_context.get("agency_id"),
            confirmed=self._is_confirmed_task(task),
        )

        emit_progress(
            state,
            "tool_result",
            self._completed_message(task),
            {
                "stage": "tool_call_completed",
                "task_id": task.get("task_id"),
            },
        )

        return self._with_execution_context(
            result=result,
            tool_name=selected_tool.name,
            arguments=arguments,
        )
