from apps.agent_runtime.llms.openai.openai_client import openai_llm
from apps.agent_runtime.agents.schemas.supervisor.tool_selector_schema import (
    ToolMetadata,
)
from apps.agent_runtime.agents.prompts.tool_selector.tool_selector import (
    tool_selection_prompt,
)


class ToolSelector:

    def __init__(self):

        structured_llm = openai_llm.with_structured_output(ToolMetadata)

        self.chain = tool_selection_prompt | structured_llm

    async def select(self, task, available_tools):
        
        # print(f"Selecting tool for task: {task} from available tools: {available_tools}")

        response = await self.chain.ainvoke(
            {"task": task, "available_tools": available_tools}
        )
        

        return response


tool_selector = ToolSelector()
