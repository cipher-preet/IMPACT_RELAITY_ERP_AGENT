from concurrent import futures
import json
import os
import grpc
import asyncio

import queue
import threading

from apps.agent_runtime.agents.constants.event_types import AssistantEventType
from apps.agent_runtime.grpc_runtime.generated import (
    ai_runtime_pb2,
    ai_runtime_pb2_grpc,
)

from apps.agent_runtime.graphs.supervisor_graph.graph import SupervisorGraph
from apps.agent_runtime.runtime.runtime_manager import RuntimeManager

from apps.agent_runtime.nodes.memory.normalizers.grpc_memory_normalizer import (
    GrpcMemoryNormalizer,
)

runtime_manager = RuntimeManager()


def safe_json_loads(value, default):
    if not value or value == "null":
        return default

    try:
        return json.loads(value)
    except Exception:
        return default


def build_stream_event(event_type: str, message: str, payload: dict | None = None):
    payload = payload or {}
    payload["message"] = message

    return ai_runtime_pb2.AssistantStreamResponse(
        event=ai_runtime_pb2.AssistantEvent(
            event_type=event_type,
            message=message,
            payload_json=json.dumps(payload, default=str),
        )
    )


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

                print("Received RunAssistant request with auth_context:", auth_context)

                graph = SupervisorGraph.build()

                # memory = GrpcMemoryNormalizer().normalize(auth_context)

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
                    "resume_context": None,
                    "execution_context": {},
                    "retry_count": {},
                    "final_response": None,
                }

                event_queue = queue.Queue()

                def progress_callback(event: dict):
                    event_queue.put(event)

                state["progress_callback"] = progress_callback

                def run_graph():
                    try:
                        result = asyncio.run(graph.ainvoke(state))
                        event_queue.put(
                            {
                                "event_type": "__final__",
                                "payload": result,
                                "message": "",
                            }
                        )
                    except Exception as exc:
                        print(f"Assistant graph execution failed: {exc}")
                        event_queue.put(
                            {
                                "event_type": AssistantEventType.RUN_FAILED.value,
                                "message": "Unable to complete the request.",
                                "payload": {
                                    "run_id": run.run_id,
                                    "stage": "graph_execution",
                                    "terminal": True,
                                },
                            }
                        )

                thread = threading.Thread(target=run_graph, daemon=True)
                thread.start()

                while True:
                    event = event_queue.get()
                    event_type = event.get("event_type")

                    if event_type == "__final__":
                        result = event.get("payload") or {}
                        final_response = result.get("final_response") or {}

                        yield ai_runtime_pb2.AssistantStreamResponse(
                            event=ai_runtime_pb2.AssistantEvent(
                                event_type=final_response.get("event_type"),
                                message=final_response.get("message"),
                                payload_json=final_response.get("payload_json"),
                            )
                        )
                        break

                    yield build_stream_event(
                        event_type=event_type,
                        message=event.get("message") or "",
                        payload={
                            "run_id": run.run_id,
                            **(event.get("payload") or {}),
                        },
                    )

                    if event_type in {
                        AssistantEventType.RUN_FAILED.value,
                        AssistantEventType.RUN_CANCELLED.value,
                    }:
                        break

                return


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
