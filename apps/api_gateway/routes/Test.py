from fastapi import APIRouter
from apps.agent_runtime.grpc_runtime.runtime.runtime_manager import (
    runtime_manager,
)
from apps.agent_runtime.agents.supervisor.graph_router import graph_router
from apps.agent_runtime.agents.planner.decomposition import decomposer


from apps.agent_runtime.mcp.client.mcp_client import (mcp_client)


router = APIRouter()


@router.post("/testEndpoint")
async def classify_intent(payload: dict):

    query = payload.get("query")

    intent = await runtime_manager.intent_classifier.classify(query)

    workflow_plan = await decomposer.decompose(query=query, intent=intent)

    # router = await graph_router.route(intent)

    # print("this is graoph route ---->>> ", router)

    return {
        "success": True,
        "plan": workflow_plan,
        # "query": query,
        # "intent": intent,
        # "route": router,
    }



@router.get("/testmcp")
async def test_mcp_connection():

    try:

        initialize_result = (
            await mcp_client.initialize()
        )

        tools_result = (
            await mcp_client.list_tools()
        )

        return {

            "success": True,

            "initialize": initialize_result,

            "tools": tools_result
        }

    except Exception as error:

        return {

            "success": False,

            "message": str(error)
        }