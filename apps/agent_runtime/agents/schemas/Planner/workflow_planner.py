from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from apps.agent_runtime.agents.constants.intents import TaskStatusEnum


class WorkflowTask(BaseModel):

    task_id: str = Field(
        description="Unique workflow task id"
    )

    domain: str = Field(
        description="Business domain"
    )

    module: str = Field(
        description="Business module"
    )

    action: str = Field(
        description="Business action"
    )

    description: str = Field(
        description="Human-readable task description"
    )

    dependencies: List[str] = Field(
        default_factory=list,
        description="Dependent task ids"
    )

    execution_order: int = Field(
        description="Execution sequence order"
    )

    required_entities: List[str] = Field(
        default_factory=list,
        description="Entities required before execution"
    )

    assigned_graph: Optional[str] = Field(
        default=None,
        description="Graph assigned by router"
    )

    status: TaskStatusEnum = Field(
        default=TaskStatusEnum.PENDING
    )


class WorkflowPlan(BaseModel):

    workflow_id: str

    tasks: List[WorkflowTask]