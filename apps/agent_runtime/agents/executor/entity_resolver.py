from apps.agent_runtime.agents.prompts.executor.entity_resolution_prompt import (
    entity_resolution_prompt,
)
from apps.agent_runtime.agents.schemas.executor.entity_resolution import (
    EntityResolutionPlan,
)
from apps.agent_runtime.llms.openai.openai_client import openai_planning_llm


class EntityResolver:

    def __init__(self):
        structured_llm = openai_planning_llm.with_structured_output(
            EntityResolutionPlan,
            method="function_calling",
        )
        self.chain = entity_resolution_prompt | structured_llm

    async def plan_resolution(
        self,
        query: str,
        task: dict,
        target_tool_name: str,
        target_tool_schema: dict,
        current_arguments: dict,
        missing_fields: list,
        memory_context: dict,
        auth_context: dict,
        available_tools: list,
    ) -> dict:
        response = await self.chain.ainvoke(
            {
                "query": query,
                "task": task,
                "target_tool_name": target_tool_name,
                "target_tool_schema": target_tool_schema,
                "current_arguments": current_arguments,
                "missing_fields": missing_fields,
                "memory_context": memory_context,
                "auth_context": auth_context,
                "available_tools": available_tools,
            }
        )

        return response.model_dump()


entity_resolver = EntityResolver()
