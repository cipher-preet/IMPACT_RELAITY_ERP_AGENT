from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CheckpointResumeDecision(BaseModel):
    can_resume: bool = Field(
        description="Whether latest user message resolves the pending task context."
    )

    resume_type: str = Field(
        description="Dynamic type like clarification, confirmation, approval, missing_input, selection, or unknown."
    )

    task_id: Optional[str] = Field(
        default=None, description="Task id if available from pending context."
    )

    resolved_payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Dynamic resolved data. Do not invent IDs or fields."
    )

    tool_name: Optional[str] = Field(
        default=None,
        description="Exact tool name from available_tools when the pending context should resume a concrete tool call.",
    )

    needs_user_input: bool = Field(
        description="Whether more user input is still required."
    )

    user_question: Optional[str] = Field(
        default=None, description="Question to ask user if still unresolved."
    )

    reason: str


class ConfirmationDecision(BaseModel):
    is_confirmation_response: bool = Field(
        description="Whether the latest user message is responding to a pending confirmation or approval request."
    )

    confirmed: bool = Field(
        description="True when the user approves/proceeds/confirms; false when they reject/cancel/deny."
    )

    needs_user_input: bool = Field(
        description="Whether the user response is ambiguous and needs a follow-up question."
    )

    reason: str
