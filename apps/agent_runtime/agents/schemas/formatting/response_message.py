from pydantic import BaseModel
from pydantic import Field


class ResponseMessage(BaseModel):

    message: str = Field(
        description="Natural, concise, user-facing assistant message."
    )
