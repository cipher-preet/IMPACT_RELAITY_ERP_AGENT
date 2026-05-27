from enum import Enum

from pydantic import BaseModel, Field


class IntentEnum(str, Enum):
    ERP_OPERATION = "ERP_OPERATION"
    SUPPORT_OPERATION = "SUPPORT_OPERATION"
    AUTOMATION_OPERATION = "AUTOMATION_OPERATION"
    GENERAL_QUERY = "GENERAL_QUERY"


class IntentClassifierResponse(BaseModel):

    intent: IntentEnum = Field(
        description="Classified user intent"
    )