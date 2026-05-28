from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from apps.agent_runtime.agents.constants.intents import (
    DomainEnum,
    ModuleEnum,
    ActionEnum,
    ExecutionTypeEnum,
    PriorityEnum,
)


class IntentClassifierResponse(BaseModel):
    domain: DomainEnum = Field(description="High-level business domain")

    module: ModuleEnum = Field(description="Business module inside domain")

    action: ActionEnum = Field(description="Requested action")

    execution_type: ExecutionTypeEnum = Field(description="Execution strategy type")

    priority: PriorityEnum = Field(
        default=PriorityEnum.MEDIUM, description="Request priority level"
    )

    requires_approval: bool = Field(
        default=False, description="Whether human approval is required"
    )

    requires_clarification: bool = Field(
        default=False, description="Whether clarification is needed"
    )

    confidence_score: float = Field(
        ge=0, le=1, description="Intent classification confidence score"
    )

    reasoning: Optional[str] = Field(
        default=None, description="Why this intent was selected"
    )
