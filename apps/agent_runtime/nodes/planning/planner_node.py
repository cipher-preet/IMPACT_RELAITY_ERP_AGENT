from apps.agent_runtime.state.graph_state import GraphState
from apps.agent_runtime.agents.planner.decomposition import decomposer
from apps.agent_runtime.runtime.progress_events import emit_progress


class PlannerNode:

    def _clean_text(self, value: object) -> str:
        return " ".join(str(value or "").replace("_", " ").split())

    def _task_label(self, task: dict) -> str:
        description = self._clean_text(task.get("description"))

        if description:
            return description.rstrip(".")

        action = self._clean_text(task.get("action")).lower()
        module = self._clean_text(task.get("module")).lower()

        if action and module:
            return f"{action} in {module}"

        return action or module or "complete the next step"

    def _plan_message(self, tasks: list) -> str:
        if not tasks:
            return "I did not find a runnable action yet, so I am preparing a response based on what I know."

        task_labels = [
            self._task_label(task)
            for task in tasks[:2]
            if isinstance(task, dict)
        ]

        if len(tasks) == 1 and task_labels:
            return f"I found the next step: {task_labels[0]}. I am checking the required information before running it."

        if task_labels:
            joined = "; ".join(task_labels)
            extra = len(tasks) - len(task_labels)
            suffix = f", plus {extra} more" if extra > 0 else ""

            return f"I found {len(tasks)} steps: {joined}{suffix}. I will handle them in order."

        return f"I found {len(tasks)} steps for this request. I will handle them in order."

    async def run(self, state: GraphState) -> GraphState:

        workflow_plan = await decomposer.decompose(
            query=state["query"],
            intent=state["intent"],
            memory_context=state.get("memory_context", {}),
        )

        state["workflow_id"] = workflow_plan.workflow_id

        state["workflow_plan"] = workflow_plan.model_dump()

        tasks = state["workflow_plan"].get("tasks", [])

        emit_progress(
            state,
            "analyzing",
            self._plan_message(tasks),
            {
                "stage": "plan_created",
                "task_count": len(tasks),
                "tasks": [
                    {
                        "task_id": task.get("task_id"),
                        "description": task.get("description"),
                        "action": task.get("action"),
                        "module": task.get("module"),
                    }
                    for task in tasks
                    if isinstance(task, dict)
                ],
            },
        )

        state["workflow_status"] = "PLANNED"

        return state
