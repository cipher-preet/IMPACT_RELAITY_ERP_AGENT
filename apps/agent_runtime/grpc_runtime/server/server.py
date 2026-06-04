from concurrent import futures
import json
import os
import grpc
import asyncio

from apps.agent_runtime.grpc_runtime.generated import (
    ai_runtime_pb2,
    ai_runtime_pb2_grpc,
)

from apps.agent_runtime.graphs.supervisor_graph.graph import SupervisorGraph
from apps.agent_runtime.runtime.runtime_manager import RuntimeManager
# runtime_manager = runtime_manager.RuntimeManager()

runtime_manager = RuntimeManager()



def safe_json_loads(value, default):
    if not value or value == "null":
        return default

    try:
        return json.loads(value)
    except Exception:
        return default


class AssistantAiService(ai_runtime_pb2_grpc.AssistantAiServiceServicer):
    
    def __init__(self, runtime_manager):
        self.runtime_manager = runtime_manager

    def RunAssistant(self, request_iterator, context):

        metadata = dict(context.invocation_metadata())

        auth_header = metadata.get("authorization")
        expected_token = os.getenv("AI_GRPC_TOKEN")

        if expected_token and auth_header != f"Bearer {expected_token}":
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid gRPC token")

        for request in request_iterator:

            if request.HasField("run_cancel"):
                yield ai_runtime_pb2.AssistantStreamResponse(
                    event=ai_runtime_pb2.AssistantEvent(
                        event_type="run_cancelled",
                        message="Run cancelled",
                        payload_json=json.dumps(
                            {
                                "run_id": request.run_cancel.run_id,
                                "reason": request.run_cancel.reason,
                            }
                        ),
                    )
                )
                return

            if request.HasField("run_start"):

                run = request.run_start

                query = run.user_message
                
                print(f"Received run start request with query ====: {query}")

                access = safe_json_loads(run.access_json, {})
                recent_messages = safe_json_loads(run.recent_messages_json, [])
                pending_task_context = safe_json_loads(
                    run.pending_task_context_json, {}
                )

                auth_context = {
                    "run_id": run.run_id,
                    "user_id": run.user_id,
                    "agency_id": run.agency_id,
                    "session_id": run.session_id,
                    "user_message": query,
                    "summary_memory": run.summary_memory or "",
                    "pending_task_context_json": json.dumps(pending_task_context or {}),
                    "recent_messages_json": json.dumps(recent_messages or []),
                    "access_json": json.dumps(access or {}),
                }

                print(
                    f"Received run start request ________________ --->>> {auth_context}"
                )

                graph = SupervisorGraph.build()

                state = {
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

                print(f"Starting run ________________ --->>> {state}")

                result = asyncio.run(graph.ainvoke(state))

                print(f"Completed run ________________ --->>> {result}")

                final_response = result.get("final_response")

                print(f"Final response ________________ --->>> {final_response}")

                yield ai_runtime_pb2.AssistantStreamResponse(
                    event=ai_runtime_pb2.AssistantEvent(
                        event_type="follow_up_question",
                        message=str(final_response),
                        payload_json=json.dumps(
                            {
                                "success": True,
                                "result": final_response,
                            }
                        ),
                    )
                )


def start_grpc_server():
    
    asyncio.run(runtime_manager.initialize())

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    ai_runtime_pb2_grpc.add_AssistantAiServiceServicer_to_server(
        AssistantAiService(runtime_manager=runtime_manager),
        server,
    )

    server.add_insecure_port("0.0.0.0:50051")

    print("\n gRPC Streaming Server Running On Port 50051\n")

    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    start_grpc_server()
