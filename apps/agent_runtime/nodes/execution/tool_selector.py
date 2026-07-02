from apps.agent_runtime.llms.openai.openai_client import openai_planning_llm
from apps.agent_runtime.agents.schemas.supervisor.tool_selector_schema import (
    ToolMetadata,
)
from apps.agent_runtime.agents.prompts.tool_selector.tool_selector import (
    tool_selection_prompt,
)


class ToolSelector:

    def __init__(self):

        structured_llm = openai_planning_llm.with_structured_output(ToolMetadata)

        self.chain = tool_selection_prompt | structured_llm

    async def select(self, task, available_tools, memory_context=None, query=None):

        response = await self.chain.ainvoke(
            {
                "task": task,
                "query": query or "",
                "available_tools": available_tools,
                "memory_context": memory_context or {},
            }
        )

        return response


tool_selector = ToolSelector()
