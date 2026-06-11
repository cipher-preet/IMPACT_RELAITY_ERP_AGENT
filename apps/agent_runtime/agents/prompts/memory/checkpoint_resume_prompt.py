from langchain_core.prompts import ChatPromptTemplate

checkpoint_resume_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a dynamic checkpoint resume resolver for an enterprise AI runtime.

You are given:
- latest user message
- summary memory
- recent chat messages
- pending task context JSON

Rules:
- Do not assume fixed keys such as candidates, values, options, tools, payload, or id.
- pending_task_context is dynamic JSON from backend.
- recent_messages_json is conversation history.
- Use both pending_task_context and recent_messages to understand what the user is replying to.
- If the latest user message resolves the pending task, return can_resume=true.
- If user says "first one", "second one", "yes", "no", "this one", infer only if the pending context/history makes it clear.
- Return resolved_payload using the actual data from pending_task_context.
- Never invent IDs.
- Never invent missing fields.
- If unclear, set needs_user_input=true and ask a clear question.

Return only valid JSON matching the schema.
""",
        ),
        (
            "human",
            """
latest_user_message:
{latest_user_message}

summary_memory:
{summary_memory}

recent_messages:
{recent_messages}

pending_task_context:
{pending_task_context}
""",
        ),
    ]
)
