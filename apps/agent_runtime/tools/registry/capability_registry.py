from collections import defaultdict


class CapabilityRegistry:

    def __init__(self):

        self.entity_tools = defaultdict(list)

        self.capability_tools = defaultdict(list)

    def build(self, tools: list):

        for tool in tools:

            entity_types = tool.get("entityTypes", [])

            capabilities = tool.get("capabilities", [])

            for entity in entity_types:

                self.entity_tools[entity].append(tool)

            for capability in capabilities:

                self.capability_tools[capability].append(tool)

    def get_entity_tools(self, entity_type: str):

        return self.entity_tools.get(entity_type, [])

    def get_capability_tools(self, capability: str):

        return self.capability_tools.get(capability, [])
