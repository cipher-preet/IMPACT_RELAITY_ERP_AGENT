import uuid

from apps.agent_runtime.llms.openai.openai_client import openai_planning_llm

from apps.agent_runtime.agents.schemas.Planner.workflow_planner import (
    WorkflowPlan
)

from apps.agent_runtime.agents.prompts.planner.decomposition import (
    decomposition_prompt,
)


class TaskDecomposer:

    def __init__(self):
        
        structured_llm = openai_planning_llm.with_structured_output(WorkflowPlan)
        self.chain = decomposition_prompt | structured_llm

    async def decompose(
        self,
        query: str,
        intent,
        memory_context: dict
    ) -> WorkflowPlan:

        response = await self.chain.ainvoke({

            "query": query,

            "intent": intent.model_dump_json(),

            "memory_context": memory_context
        })

        response.workflow_id = str(
            uuid.uuid4()
        )

        return response
    
decomposer = TaskDecomposer()
