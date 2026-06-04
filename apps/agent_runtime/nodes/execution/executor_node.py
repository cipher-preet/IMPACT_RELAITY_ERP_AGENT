from datetime import datetime
from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.agents.executor.parallel_executor import ParallelExecutor
from apps.agent_runtime.agents.executor.execution_supervisor import ExecutionSupervisor
from apps.agent_runtime.nodes.human_in_the_loop.hitl_builder import HITLBuilder


class ExecutorNode:

    def __init__(self):

        self.parallel_executor = ParallelExecutor()
        self.supervisor = ExecutionSupervisor()

    def _is_hitl_task(self, task: dict) -> bool:
        action = str(task.get("action", "")).upper()
        module = str(task.get("module", "")).upper()
        execution_type = str(task.get("execution_type", "")).upper()
        return (
            action
            in [
                "REQUEST_CLARIFICATION",
                "CLARIFY",
                "REQUEST_APPROVAL",
                "APPROVE",
                "REQUEST_CONFIRMATION",
                "CONFIRM",
            ]
            or module
            in [
                "APPROVAL",
                "HUMAN_APPROVAL",
                "CLARIFICATION",
                "COMMUNICATION",
            ]
            or execution_type
            in [
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

        task_id = task["task_id"]

        human_input = hitl_result["human_input"]

        state["current_task_id"] = task_id
        state["workflow_status"] = "WAITING_FOR_USER"
        state["waiting_for_user_input"] = True
        state["pending_human_input"] = human_input

        state.setdefault("pending_clarifications", [])
        state["pending_clarifications"].append(human_input)

        state["task_results"][task_id] = hitl_result

        state["execution_logs"].append(
            {
                "task_id": task_id,
                "status": "WAITING_FOR_USER",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        return state

    def _is_human_loop_required(self, result: dict) -> bool:

        if not isinstance(result, dict):
            return False

        if result.get("requires_human_input") is True:
            return True

        if result.get("status") == "WAITING_FOR_USER":
            return True

        structured = result.get("result", {}).get("structuredContent", {})

        data = structured.get("data", {})

        candidates = data.get("candidates")

        if isinstance(candidates, list) and len(candidates) > 1:
            return True

        return False

    async def run(self, state: GraphState) -> GraphState:

        if state.get("waiting_for_user_input"):
            state["workflow_status"] = "WAITING_FOR_USER"
            return state

        state["workflow_status"] = "RUNNING"

        while True:

            executable_tasks = self.supervisor.get_executable_tasks(state)

            if not executable_tasks:
                break

            # IMPORTANT:
            # Handle HITL tasks before MCP/tool execution.
            for task in executable_tasks:

                if self._is_hitl_task(task):

                    hitl_result = HITLBuilder.build_from_task(task)

                    return self._apply_human_loop_state(
                        state=state,
                        task=task,
                        hitl_result=hitl_result,
                    )

            normal_tasks = [
                task for task in executable_tasks if not self._is_hitl_task(task)
            ]

            if not normal_tasks:
                break

            results = await self.parallel_executor.execute_tasks(
                normal_tasks,
                state,
            )

            for task, result in zip(normal_tasks, results):

                task_id = task["task_id"]
                state["current_task_id"] = task_id

                if isinstance(result, Exception):

                    state["failed_tasks"].append(task_id)

                    state["task_results"][task_id] = {"error": str(result)}

                    state["execution_logs"].append(
                        {
                            "task_id": task_id,
                            "status": "FAILED",
                            "error": str(result),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                    continue

                if self._is_human_loop_required(result):

                    hitl_result = {
                        "requires_human_input": True,
                        "status": "WAITING_FOR_USER",
                        "human_input": {
                            "id": f"hitl_{task_id}",
                            "type": "OPTION_SELECTION",
                            "task_id": task_id,
                            "message": "Multiple matching records found. Please select one.",
                            "options": (
                                result.get("result", {})
                                .get("structuredContent", {})
                                .get("data", {})
                                .get("candidates", [])
                            ),
                            "metadata": {"tool_result": result},
                            "status": "PENDING",
                            "created_at": datetime.utcnow().isoformat(),
                        },
                    }

                    return self._apply_human_loop_state(
                        state=state,
                        task=task,
                        hitl_result=hitl_result,
                    )

                state["completed_tasks"].append(task_id)
                state["task_results"][task_id] = result

                state["execution_logs"].append(
                    {
                        "task_id": task_id,
                        "status": "SUCCESS",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        total_tasks = len(state["workflow_plan"].get("tasks", []))

        if state.get("failed_tasks"):
            state["workflow_status"] = "FAILED"

        elif len(state.get("completed_tasks", [])) >= total_tasks:
            state["workflow_status"] = "COMPLETED"

        else:
            state["workflow_status"] = "RUNNING"

        return state
