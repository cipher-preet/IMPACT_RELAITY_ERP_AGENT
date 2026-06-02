from datetime import datetime

from apps.agent_runtime.state.graph_state import GraphState

from apps.agent_runtime.agents.executor.parallel_executor import ParallelExecutor

from apps.agent_runtime.agents.executor.execution_supervisor import ExecutionSupervisor


class ExecutorNode:

    def __init__(self):

        self.parallel_executor = ParallelExecutor()

        self.supervisor = ExecutionSupervisor()

    async def run(self, state: GraphState) -> GraphState:

        state["workflow_status"] = "RUNNING"

        while True:

            executable_tasks = self.supervisor.get_executable_tasks(state)

            print("COMPLETED:", state["completed_tasks"])

            print("FAILED:", state["failed_tasks"])

            if not executable_tasks:

                print("No executable tasks left.")

                break

            results = await self.parallel_executor.execute_tasks(
                executable_tasks, state
            )

            for task, result in zip(executable_tasks, results):

                task_id = task["task_id"]

                print(f"\nTASK: {task_id}")

                print("RESULT TYPE:", type(result))

                print("RESULT:", result)

                state["current_task_id"] = task_id

                if isinstance(result, Exception):

                    print(f"FAILED TASK: {task_id}")

                    print(f"ERROR: {repr(result)}")

                    state["failed_tasks"].append(task_id)

                    state["task_results"][task_id] = {"error": str(result)}

                    continue

                state["completed_tasks"].append(task_id)

                state["task_results"][task_id] = result

                state["execution_logs"].append(
                    {
                        "task_id": task_id,
                        "status": "SUCCESS",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        state["workflow_status"] = "COMPLETED"

        return state
