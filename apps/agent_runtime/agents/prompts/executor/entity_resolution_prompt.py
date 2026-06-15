from langchain_core.prompts import ChatPromptTemplate

entity_resolution_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You plan how to resolve a missing ID required by a business tool.

The user may provide a human-readable name, label, title, email, or phrase instead of an internal ID.
Do not ask the user for internal IDs if a resolver tool can find them.

Rules:
- Use only available_tools.
- Never choose assistant/meta tools.
- Prefer tools in the same domain/entity family as the target tool.
- Prefer list/search/get tools that can return candidate records.
- Use auth_context values only for schema fields that require them.
- Set needs_resolution=true only when an ID-like missing field can be resolved.
- target_field must be one of missing_fields.
- lookup_value must be the human value to match against resolver results.
- resolver_arguments must use only fields from the resolver tool input schema.
- Do not invent IDs.
- Return structured output only.
            """,
        ),
        (
            "human",
            """
User Query:
{query}

Task:
{task}

Target Tool Name:
{target_tool_name}

Target Tool Schema:
{target_tool_schema}

Current Arguments:
{current_arguments}

Missing Fields:
{missing_fields}

Memory Context:
{memory_context}

Auth Context:
{auth_context}

Available Tools:
{available_tools}
            """,
        ),
    ]
)
