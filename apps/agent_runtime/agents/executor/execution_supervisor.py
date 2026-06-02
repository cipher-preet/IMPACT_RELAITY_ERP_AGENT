from apps.agent_runtime.state.graph_state import GraphState


class ExecutionSupervisor:

    def get_executable_tasks(self, state: GraphState):

        executable_tasks = []

        tasks = state["workflow_plan"].get("tasks", [])


        processed = set(state["completed_tasks"] + state["failed_tasks"])

        for task in tasks:

            if task["task_id"] in processed:
                continue

            dependencies = task.get("dependencies", [])

            if all(dep in processed for dep in dependencies):
                executable_tasks.append(task)

        return executable_tasks
