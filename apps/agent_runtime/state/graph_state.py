from typing import TypedDict,Optional,Dict,Any,List

class GraphState(TypedDict,total=False):
    query: str
    auth_context: Dict[str, Any]
    intent: str
    selected_graph: str
    execution_plan: List[Dict[str, Any]]
    tool_results: Dict[str, Any]
    final_response: str
    error: Optional[str]
    metadata: Dict[str, Any]