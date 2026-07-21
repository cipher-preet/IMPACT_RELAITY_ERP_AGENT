from datetime import datetime
from typing import Any, Dict, List, Optional

from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.agents.executor.parallel_executor import ParallelExecutor
from apps.agent_runtime.agents.executor.execution_supervisor import ExecutionSupervisor


class ExecutorNode:

    DEFAULT_MAX_RETRIES = 3

    def __init__(self):
        self.parallel_executor = ParallelExecutor()
        self.supervisor = ExecutionSupervisor()

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def _ensure_state_defaults(self, state: GraphState) -> GraphState:
        defaults = {
            "workflow_plan": {},
            "completed_tasks": [],
            "failed_tasks": [],
            "task_results": {},
            "execution_logs": [],
            "pending_clarifications": [],
            "human_input_history": [],
            "retry_count": {},
            "resolved_entities": {},
            "memory_context": {},
            "resume_context": None,
            "execution_context": {},
            "auth_context": {},
            "waiting_for_user_input": False,
            "pending_human_input": None,
        }

        for key, default_value in defaults.items():
            state[key] = state.get(key) or default_value

        return state

    def _extract_structured_content(
        self,
        result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:

        if not isinstance(result, dict):
            return {}

        result_data = result.get("result") or {}

        if not isinstance(result_data, dict):
            return {}

        structured = result_data.get("structuredContent") or {}

        if not isinstance(structured, dict):
            return {}

        return structured

    def _extract_data(
        self,
        result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:

        structured = self._extract_structured_content(result)
        data = structured.get("data") or {}

        return data if isinstance(data, dict) else {}

    def _extract_status(
        self,
        result: Optional[Dict[str, Any]],
    ) -> str:

        structured = self._extract_structured_content(result)

        return str(structured.get("status") or "").lower()

    def _is_failed_result(
        self,
        result: Optional[Dict[str, Any]],
    ) -> bool:

        status = self._extract_status(result)

        if status in {"error", "failed", "failure"}:
            return True

        if isinstance(result, dict) and result.get("success") is False:
            return True

        structured = self._extract_structured_content(result)

        return structured.get("success") is False

    def _result_error(
        self,
        result: Optional[Dict[str, Any]],
    ) -> Exception:

        if not isinstance(result, dict):
            return RuntimeError("Task execution returned an invalid result.")

        structured = self._extract_structured_content(result)
        message = (
            structured.get("message")
            or structured.get("error")
            or result.get("message")
            or result.get("error")
            or "Task execution failed."
        )

        return RuntimeError(str(message))

    def _max_retries_for_task(self, task: Dict[str, Any]) -> int:

        retry_policy = task.get("retry_policy") or {}
        max_retries = retry_policy.get("max_retries", self.DEFAULT_MAX_RETRIES)

        try:
            return max(0, int(max_retries))
        except (TypeError, ValueError):
            return self.DEFAULT_MAX_RETRIES

    def _register_retry(
        self,
        state: GraphState,
        task: Dict[str, Any],
        error: Exception,
    ) -> bool:

        task_id = task.get("task_id") or "unknown_task"
        retry_count = state["retry_count"].get(task_id, 0)
        max_retries = self._max_retries_for_task(task)

        if retry_count >= max_retries:
            return False

        next_retry_count = retry_count + 1
        state["retry_count"][task_id] = next_retry_count

        state["execution_logs"].append(
            {
                "task_id": task_id,
                "status": "RETRYING",
                "retry_count": next_retry_count,
                "max_retries": max_retries,
                "error": str(error),
                "timestamp": self._now(),
            }
        )

        return True

    def _extract_options(
        self,
        result: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        data = self._extract_data(result)

        for value in data.values():
            if isinstance(value, list):
                return value

        return []

    def _is_hitl_task(self, task: Dict[str, Any]) -> bool:
        if not isinstance(task, dict):
            return False

        execution = task.get("execution") or {}
        human_loop = task.get("human_loop") or {}

        mode = str(execution.get("mode") or "").upper()
        trigger = str(human_loop.get("trigger") or "").upper()

        return mode in {
            "HUMAN_INPUT",
            "APPROVAL",
            "CONFIRMATION",
        } or (human_loop.get("enabled") is True and trigger == "ALWAYS")

    def _is_human_loop_required(
        self,
        task: Dict[str, Any],
        result: Optional[Dict[str, Any]],
    ) -> bool:

        if not isinstance(task, dict):
            return False

        human_loop = task.get("human_loop") or {}

        if human_loop.get("enabled") is not True:
            return False

        trigger = str(human_loop.get("trigger") or "").upper()

        if trigger == "ALWAYS":
            return True

        if trigger == "MULTIPLE_RESULTS":
            return len(self._extract_options(result)) > 1

        if trigger == "SINGLE_RESULT":
            return len(self._extract_options(result)) == 1

        if trigger == "NO_RESULTS":
            return len(self._extract_options(result)) == 0

        if trigger == "TOOL_REQUIRES_INPUT":
            structured = self._extract_structured_content(result)
            status = str(structured.get("status") or "").lower()

            return status in {
                "requires_input",
                "requires_confirmation",
            }

        return False

    def _build_hitl_result(
        self,
        task: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        task_id = task.get("task_id") or "unknown_task"
        human_loop = task.get("human_loop") or {}

        input_type = human_loop.get("input_type") or "INPUT"
        message = human_loop.get("message") or "Please provide input to continue."

        return {
            "requires_human_input": True,
            "status": "WAITING_FOR_USER",
            "human_input": {
                "id": f"hitl_{task_id}",
                "type": input_type,
                "task_id": task_id,
                "message": message,
                "options": self._extract_options(result),
                "metadata": {
                    "task": task,
                    "tool_result": result,
                },
                "status": "PENDING",
                "created_at": self._now(),
            },
        }

    def _apply_human_loop_state(
        self,
        state: GraphState,
        task: Dict[str, Any],
        hitl_result: Dict[str, Any],
    ) -> GraphState:

        state = self._ensure_state_defaults(state)

        task_id = task.get("task_id") or "unknown_task"
        human_input = hitl_result.get("human_input") or {}

        state["current_task_id"] = task_id
        state["workflow_status"] = "WAITING_FOR_USER"
        state["waiting_for_user_input"] = True
        state["pending_human_input"] = human_input
        state["pending_clarifications"].append(human_input)
        state["task_results"][task_id] = hitl_result

        state["execution_logs"].append(
            {
                "task_id": task_id,
                "status": "WAITING_FOR_USER",
                "timestamp": self._now(),
            }
        )

        return state

    def _mark_success(
        self,
        state: GraphState,
        task: Dict[str, Any],
        result: Any,
    ) -> None:

        task_id = task.get("task_id") or "unknown_task"

        if task_id not in state["completed_tasks"]:
            state["completed_tasks"].append(task_id)

        state["task_results"][task_id] = result

        state["execution_logs"].append(
            {
                "task_id": task_id,
                "status": "SUCCESS",
                "timestamp": self._now(),
            }
        )

    def _mark_failed(
        self,
        state: GraphState,
        task: Dict[str, Any],
        error: Exception,
    ) -> None:

        task_id = task.get("task_id") or "unknown_task"

        if task_id not in state["failed_tasks"]:
            state["failed_tasks"].append(task_id)

        state["task_results"][task_id] = {
            "error": str(error),
        }

        state["execution_logs"].append(
            {
                "task_id": task_id,
                "status": "FAILED",
                "error": str(error),
                "timestamp": self._now(),
            }
        )

    def _finalize_status(self, state: GraphState) -> None:
        tasks = state.get("workflow_plan", {}).get("tasks") or []
        total_tasks = len(tasks)

        if state["failed_tasks"]:
            state["workflow_status"] = "FAILED"
            return

        if total_tasks == 0:
            state["workflow_status"] = "COMPLETED"
            return

        if total_tasks > 0 and len(state["completed_tasks"]) >= total_tasks:
            state["workflow_status"] = "COMPLETED"
            return

        pending_tasks = [
            task
            for task in tasks
            if isinstance(task, dict)
            and task.get("task_id") not in state["completed_tasks"]
            and task.get("task_id") not in state["failed_tasks"]
        ]

        for task in pending_tasks:
            task_id = task.get("task_id") or "unknown_task"
            if task_id not in state["failed_tasks"]:
                state["failed_tasks"].append(task_id)

            state["task_results"][task_id] = {
                "error": "Task could not run because its dependencies were not satisfied.",
            }

            state["execution_logs"].append(
                {
                    "task_id": task_id,
                    "status": "FAILED",
                    "error": "No executable tasks available.",
                    "timestamp": self._now(),
                }
            )

        state["workflow_status"] = "FAILED"
        
        
    # --> This is the Entry Point <<--
    async def run(self, state: GraphState) -> GraphState:

        state = self._ensure_state_defaults(state)

        if state.get("waiting_for_user_input"):
            state["workflow_status"] = "WAITING_FOR_USER"
            return state

        state["workflow_status"] = "RUNNING"

        while True:
            executable_tasks = self.supervisor.get_executable_tasks(state) or []

            if not executable_tasks:
                break

            hitl_tasks = [
                task
                for task in executable_tasks
                if isinstance(task, dict) and self._is_hitl_task(task)
            ]

            if hitl_tasks:
                task = hitl_tasks[0]
                hitl_result = self._build_hitl_result(task)

                return self._apply_human_loop_state(
                    state=state,
                    task=task,
                    hitl_result=hitl_result,
                )

            normal_tasks = [
                task
                for task in executable_tasks
                if isinstance(task, dict) and not self._is_hitl_task(task)
            ]

            if not normal_tasks:
                break

            try:
                results = await self.parallel_executor.execute_tasks(
                    normal_tasks,
                    state,
                )

            except Exception as exc:
                has_retry = False

                for task in normal_tasks:
                    if self._register_retry(state, task, exc):
                        has_retry = True
                        continue

                    self._mark_failed(state, task, exc)

                if has_retry:
                    continue

                break

            task_results = list(results or [])

            if len(task_results) < len(normal_tasks):
                missing_count = len(normal_tasks) - len(task_results)
                task_results.extend(
                    RuntimeError("Task execution did not return a result.")
                    for _ in range(missing_count)
                )

            for task, result in zip(normal_tasks, task_results):
                state["current_task_id"] = task.get("task_id") or "unknown_task"

                if isinstance(result, Exception):
                    if self._register_retry(state, task, result):
                        continue

                    self._mark_failed(state, task, result)
                    continue

                if self._is_human_loop_required(task, result):
                    hitl_result = self._build_hitl_result(
                        task=task,
                        result=result,
                    )

                    return self._apply_human_loop_state(
                        state=state,
                        task=task,
                        hitl_result=hitl_result,
                    )

                if self._is_failed_result(result):
                    error = self._result_error(result)

                    if self._register_retry(state, task, error):
                        continue

                    self._mark_failed(state, task, error)
                    continue

                self._mark_success(state, task, result)

        self._finalize_status(state)

        return state
