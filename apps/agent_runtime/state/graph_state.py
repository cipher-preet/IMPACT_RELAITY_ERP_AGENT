from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import TypedDict


class GraphState(TypedDict):
    workflow_id: str
    query: str
    
    run_id: str
    user_id: str
    agency_id: str
    session_id: str
    
    intent: Dict[str, Any]
    auth_context: Dict
    workflow_plan: Dict
    current_task_id: Optional[str]
    resolved_entities: Dict

    waiting_for_user_input: bool
    pending_human_input: Optional[Dict[str, Any]]
    human_input_history: List[Dict[str, Any]]
    progress_callback: Optional[Callable[[Dict[str, Any]], None]]

    pending_clarifications: List[Dict]
    completed_tasks: List[str]
    failed_tasks: List[str]
    task_results: Dict[str, Any]
    execution_logs: List[Dict]
    workflow_status: str
    active_graph: Optional[str]
    memory_context: Dict
    resume_context: Optional[Dict[str, Any]]
    execution_context: Dict[str, Any]
    retry_count: Dict[str, int]

    final_response: Optional[Dict[str, Any]]
    
    checkpoint: Optional[Dict[str, Any]]

    access:Optional[Dict[str,Any]]
