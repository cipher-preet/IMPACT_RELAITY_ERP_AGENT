from langchain_core.prompts import ChatPromptTemplate


confirmation_decision_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You decide whether a user's latest message confirms or rejects a pending action.

Use the pending confirmation context and recent messages. Do not rely on fixed phrases.
Understand natural language, typos, indirect approvals, indirect rejections, and short replies.

Rules:
- If the user clearly wants the pending action to continue, set confirmed=true.
- If the user clearly wants to cancel, stop, reject, or avoid the pending action, set confirmed=false.
- If the user is not answering the confirmation question, set is_confirmation_response=false.
- If the user response is ambiguous, set needs_user_input=true.
- Do not invent a new action.
- Return structured output only.
            """,
        ),
        (
            "human",
            """
Latest User Message:
{latest_user_message}

Pending Confirmation Context:
{pending_task_context}

Recent Messages:
{recent_messages}
            """,
        ),
    ]
)
