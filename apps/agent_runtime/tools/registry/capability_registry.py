from collections import defaultdict


class CapabilityRegistry:

    def __init__(self):

        self.entity_tools = defaultdict(list)

        self.capability_tools = defaultdict(list)

        self.action_tools = {}

    def build(self, tools: list):

        for tool in tools:

            for entity in tool.get("entityTypes", []):

                self.entity_tools[entity].append(tool)

            for capability in tool.get("capabilities", []):

                self.capability_tools[capability].append(tool)

            module = tool.get("module")

            action = tool.get("action")

            if module and action:

                self.action_tools[(module, action)] = tool

    def get_tool_for_action(self, module, action):

        return self.action_tools.get((module, action))
