from apps.agent_runtime.agents.prompts.executor.argument_generation_prompt import (
    argument_generation_prompt,
)
from apps.agent_runtime.llms.openai.openai_client import openai_llm
from apps.agent_runtime.agents.schemas.executor.argument_generation import (
    ArgumentGenerationResponse,
)


class ArgumentGenerator:

    def __init__(self):

        structured_llm = openai_llm.with_structured_output(
            ArgumentGenerationResponse, method="function_calling"
        )

        self.chain = argument_generation_prompt | structured_llm

    async def generate_arguments(
        self,
        query: str,
        tool_name: str,
        tool_schema: dict,
        resolved_entities: dict,
        auth_context: dict,
    ):

        response = await self.chain.ainvoke(
            {
                "query": query,
                "tool_name": tool_name,
                "tool_schema": tool_schema,
                "resolved_entities": resolved_entities,
                "auth_context": auth_context,
            }
        )

        print(f"Generated arguments for tool {response}")
        return response.model_dump()


argument_generator = ArgumentGenerator()
