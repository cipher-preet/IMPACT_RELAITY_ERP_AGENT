from langchain_protocol import Any
from typing import Dict
from pydantic import BaseModel


class ToolMetadata(BaseModel):
    name: str
    arguments: str = "{}"
    description: str
    confidence_score: float
    selection_reason: str
