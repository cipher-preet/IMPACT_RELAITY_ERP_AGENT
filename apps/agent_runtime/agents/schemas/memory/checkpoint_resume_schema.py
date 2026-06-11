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

    needs_user_input: bool = Field(
        description="Whether more user input is still required."
    )

    user_question: Optional[str] = Field(
        default=None, description="Question to ask user if still unresolved."
    )

    reason: str
