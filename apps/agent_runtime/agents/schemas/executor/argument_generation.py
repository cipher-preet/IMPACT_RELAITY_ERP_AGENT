from typing import Any
from typing import Dict
from typing import List
from pydantic import BaseModel


class ArgumentGenerationResponse(BaseModel):

    arguments: Dict[str, Any]

    needs_clarification: bool = False

    missing_fields: List[str] = []