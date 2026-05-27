from langchain_core.prompts import ChatPromptTemplate


intent_classifier_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
        You are an enterprise AI supervisor.

        Your job is to classify the user intent.

        Available intents:
        - ERP_OPERATION
        - SUPPORT_OPERATION
        - AUTOMATION_OPERATION
        - GENERAL_QUERY

        Return ONLY the intent name.
        """
    ),
    (
        "human",
        "{query}"
    )
])