from apps.agent_runtime.llms.openai.openai_client import openai_llm

from apps.agent_runtime.agents.prompts.supervisor.intent_classifier_prompt import (
    intent_classifier_prompt,
)

from apps.agent_runtime.agents.schemas.supervisor.intent_classifier_schema import (
    IntentClassifierResponse,
)


class IntentClassifier:

    def __init__(self):

        structured_llm = openai_llm.with_structured_output(IntentClassifierResponse)

        self.chain = intent_classifier_prompt | structured_llm

    async def classify(self, query: str) -> str:

        response = await self.chain.ainvoke({"query": query})

        return response
