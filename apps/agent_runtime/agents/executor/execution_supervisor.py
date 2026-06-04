from apps.agent_runtime.state.graph_state import GraphState


class ExecutionSupervisor:

    def get_executable_tasks(self, state: GraphState):

        executable_tasks = []

        tasks = state["workflow_plan"].get("tasks", [])

        completed = set(state.get("completed_tasks", []))
        failed = set(state.get("failed_tasks", []))

        for task in tasks:

            task_id = task["task_id"]

            if task_id in completed or task_id in failed:
                continue

            dependencies = task.get("dependencies", [])

            if all(dep in completed for dep in dependencies):
                executable_tasks.append(task)

        return executable_tasks
