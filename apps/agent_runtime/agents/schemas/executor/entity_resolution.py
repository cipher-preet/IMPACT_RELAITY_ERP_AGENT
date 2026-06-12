from typing import Any, Dict, Optional

from pydantic import BaseModel


class EntityResolutionPlan(BaseModel):

    needs_resolution: bool = False

    target_field: Optional[str] = None

    lookup_value: Optional[str] = None

    resolver_tool_name: Optional[str] = None

    resolver_arguments: Dict[str, Any] = {}

    reason: str = ""
