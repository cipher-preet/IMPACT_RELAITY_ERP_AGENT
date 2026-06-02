from apps.agent_runtime.tools.registry.capability_registry import CapabilityRegistry


class CapabilityResolver:

    def __init__(self):

        self.registry = CapabilityRegistry()

    def resolve(self, task):

        tool = self.registry.get_tool_for_action(
            module=task["module"], action=task["action"]
        )

        if not tool:

            raise ValueError(
                f"No tool found for " f"{task['module']} " f"{task['action']}"
            )

        return tool
