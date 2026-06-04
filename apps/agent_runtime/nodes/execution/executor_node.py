from datetime import datetime
from typing import Any, Dict, List

from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.agents.executor.parallel_executor import ParallelExecutor
from apps.agent_runtime.agents.executor.execution_supervisor import ExecutionSupervisor
from apps.agent_runtime.nodes.human_in_the_loop.hitl_builder import HITLBuilder


class ExecutorNode:

    def __init__(self):
        self.parallel_executor = ParallelExecutor()
        self.supervisor = ExecutionSupervisor()

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def _ensure_state_defaults(self, state: GraphState) -> GraphState:
        state["workflow_plan"] = state.get("workflow_plan") or {}
        state["completed_tasks"] = state.get("completed_tasks") or []
        state["failed_tasks"] = state.get("failed_tasks") or []
        state["task_results"] = state.get("task_results") or {}
        state["execution_logs"] = state.get("execution_logs") or []
        state["pending_clarifications"] = state.get("pending_clarifications") or []
        state["human_input_history"] = state.get("human_input_history") or []
        state["retry_count"] = state.get("retry_count") or {}
        state["resolved_entities"] = state.get("resolved_entities") or {}
        state["memory_context"] = state.get("memory_context") or {}
        state["auth_context"] = state.get("auth_context") or {}
        return state

    def _safe_get_candidates(self, result: Any) -> List[Dict[str, Any]]:
        if not isinstance(result, dict):
            return []

        result_data = result.get("result") or {}

        if not isinstance(result_data, dict):
            return []

        structured = result_data.get("structuredContent") or {}

        if not isinstance(structured, dict):
            return []

        data = structured.get("data") or {}

        if not isinstance(data, dict):
            return []

        candidates = data.get("candidates") or []

        if not isinstance(candidates, list):
            return []

        return candidates

    def _is_hitl_task(self, task: dict) -> bool:
        if not isinstance(task, dict):
            return False

        action = str(task.get("action") or "").upper()
        module = str(task.get("module") or "").upper()
        execution_type = str(task.get("execution_type") or "").upper()

        return (
            action in [
                "REQUEST_CLARIFICATION",
                "CLARIFY",
                "REQUEST_APPROVAL",
                "APPROVE",
                "REQUEST_CONFIRMATION",
                "CONFIRM",
            ]
            or module in [
                "APPROVAL",
                "HUMAN_APPROVAL",
                "CLARIFICATION",
                "COMMUNICATION",
            ]
            or execution_type in [
                "HUMAN_APPROVAL",
                "HUMAN_INPUT",
            ]
        )

    def _apply_human_loop_state(
        self,
        state: GraphState,
        task: dict,
        hitl_result: dict,
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

        state["execution_logs"].append({
            "task_id": task_id,
            "status": "WAITING_FOR_USER",
            "timestamp": self._now(),
        })

        return state

    def _is_human_loop_required(self, result: dict) -> bool:
        if not isinstance(result, dict):
            return False

        if result.get("requires_human_input") is True:
            return True

        if result.get("status") == "WAITING_FOR_USER":
            return True

        candidates = self._safe_get_candidates(result)

        return len(candidates) > 1

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

            for task in executable_tasks:

                if not isinstance(task, dict):
                    continue

                if self._is_hitl_task(task):

                    hitl_result = HITLBuilder.build_from_task(task) or {}

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
                for task in normal_tasks:
                    task_id = task.get("task_id") or "unknown_task"

                    if task_id not in state["failed_tasks"]:
                        state["failed_tasks"].append(task_id)

                    state["task_results"][task_id] = {
                        "error": str(exc)
                    }

                    state["execution_logs"].append({
                        "task_id": task_id,
                        "status": "FAILED",
                        "error": str(exc),
                        "timestamp": self._now(),
                    })

                break

            results = results or []

            for task, result in zip(normal_tasks, results):

                task_id = task.get("task_id") or "unknown_task"
                state["current_task_id"] = task_id

                if isinstance(result, Exception):

                    if task_id not in state["failed_tasks"]:
                        state["failed_tasks"].append(task_id)

                    state["task_results"][task_id] = {
                        "error": str(result)
                    }

                    state["execution_logs"].append({
                        "task_id": task_id,
                        "status": "FAILED",
                        "error": str(result),
                        "timestamp": self._now(),
                    })

                    continue

                if self._is_human_loop_required(result):

                    candidates = self._safe_get_candidates(result)

                    hitl_result = {
                        "requires_human_input": True,
                        "status": "WAITING_FOR_USER",
                        "human_input": {
                            "id": f"hitl_{task_id}",
                            "type": "OPTION_SELECTION",
                            "task_id": task_id,
                            "message": "Multiple matching records found. Please select one.",
                            "options": candidates,
                            "metadata": {
                                "tool_result": result
                            },
                            "status": "PENDING",
                            "created_at": self._now(),
                        },
                    }

                    return self._apply_human_loop_state(
                        state=state,
                        task=task,
                        hitl_result=hitl_result,
                    )

                if task_id not in state["completed_tasks"]:
                    state["completed_tasks"].append(task_id)

                state["task_results"][task_id] = result

                state["execution_logs"].append({
                    "task_id": task_id,
                    "status": "SUCCESS",
                    "timestamp": self._now(),
                })

        tasks = state.get("workflow_plan", {}).get("tasks") or []
        total_tasks = len(tasks)

        if state["failed_tasks"]:
            state["workflow_status"] = "FAILED"

        elif total_tasks > 0 and len(state["completed_tasks"]) >= total_tasks:
            state["workflow_status"] = "COMPLETED"

        else:
            state["workflow_status"] = "RUNNING"

        return state