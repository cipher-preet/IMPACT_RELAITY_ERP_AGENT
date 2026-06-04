from fastapi import APIRouter
from langgraph import graph
from apps.agent_runtime.graphs.supervisor_graph.graph import SupervisorGraph
from apps.agent_runtime.grpc_runtime.runtime.runtime_manager import (
    runtime_manager,
)
from apps.agent_runtime.agents.supervisor.graph_router import graph_router
from apps.agent_runtime.agents.planner.decomposition import decomposer
from apps.agent_runtime.mcp.client.mcp_client import mcp_client

router = APIRouter()


@router.post("/testEndpoint")
async def classify_intent(payload: dict):

    query = payload.get("query")

    intent = await runtime_manager.intent_classifier.classify(query)
    # print(f"Classified intent: {intent}")
    workflow_plan = await decomposer.decompose(query=query, intent=intent)
    # router = await graph_router.route(intent)
    auth_context = {
        "run_id": "3467b548-8117-4cc2-bc68-3ebe471f0163",
        "user_id": "",
        "agency_id": "df5d452e-9254-45fc-b094-2715d9c26c0e",
        "session_id": "",
        "user_message": query,
        "summary_memory": "",
        "pending_task_context_json": "",
        "recent_messages_json": "",
        "access_json": "",
    }

    graph = SupervisorGraph.build()

    result = await graph.ainvoke(
        {
            "workflow_id": "wf_123",
            "query": query,
            "intent": {},
            "auth_context": auth_context,
            "workflow_plan": {},
            "current_task_id": None,
            "resolved_entities": {},
            "waiting_for_user_input": False,
            "pending_human_input": None,
            "human_input_history": [],
            "pending_clarifications": [],
            "completed_tasks": [],
            "failed_tasks": [],
            "task_results": {},
            "execution_logs": [],
            "workflow_status": "PENDING",
            "active_graph": "erp",
            "memory_context": {},
            "retry_count": {},
            "final_response": None,
        }
    )

    return {
        "success": True,
        "result": result.get("final_response"),
        # "plan": workflow_plan,
        # "query": query,
        # "intent": intent,
        # "route": router,
    }


@router.get("/testmcp")
async def test_mcp_connection():

    try:

        initialize_result = await mcp_client.initialize()

        tools_result = await mcp_client.list_tools()

        return {"success": True, "initialize": initialize_result, "tools": tools_result}

    except Exception as error:

        return {"success": False, "message": str(error)}
