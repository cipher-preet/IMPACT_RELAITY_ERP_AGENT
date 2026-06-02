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

    workflow_plan = await decomposer.decompose(query=query, intent=intent)

    graph = SupervisorGraph.build()


    result = await graph.ainvoke(
        {
            "workflow_id": "wf_123",
            "query": "give me rahul pankaj name",
            "intent": {},
            # "auth_context": auth_context,
            "workflow_plan": {},
            "current_task_id": None,
            "resolved_entities": {},
            "pending_clarifications": [],
            "completed_tasks": [],
            "failed_tasks": [],
            "task_results": {},
            "execution_logs": [],
            "workflow_status": "PENDING",
            "active_graph": "erp",
            "memory_context": {},
            "retry_count": {},
        }
    )

    # router = await graph_router.route(intent)

    # print("this is graoph route ---->>> ", router)

    return {
        "success": True,
        "result": result,
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
