from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import TypedDict


class GraphState(TypedDict):
    workflow_id: str
    query: str
    intent: Dict[str, Any]
    auth_context: Dict
    workflow_plan: Dict
    current_task_id: Optional[str]
    resolved_entities: Dict

    waiting_for_user_input: bool
    pending_human_input: Optional[Dict[str, Any]]
    human_input_history: List[Dict[str, Any]]

    pending_clarifications: List[Dict]
    completed_tasks: List[str]
    failed_tasks: List[str]
    task_results: Dict[str, Any]
    execution_logs: List[Dict]
    workflow_status: str
    active_graph: Optional[str]
    memory_context: Dict
    retry_count: Dict[str, int]

    final_response: None
