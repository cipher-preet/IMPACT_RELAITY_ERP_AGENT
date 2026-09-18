from concurrent import futures
import json
import logging
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

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def safe_json_loads(value, default):
    if not value or value == "null":
        return default

    try:
        return json.loads(value)
    except Exception:
        logger.exception("Failed to parse JSON value from gRPC request: %r", value)
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
        safe_metadata = {
            key: ("<redacted>" if key.lower() == "authorization" else value)
            for key, value in metadata.items()
        }
        logger.info("RunAssistant stream opened metadata=%s", safe_metadata)

        auth_header = metadata.get("authorization")
        expected_token = os.getenv("AI_GRPC_TOKEN")

        if expected_token and auth_header != f"Bearer {expected_token}":
            logger.warning("RunAssistant rejected because gRPC token is invalid")
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid gRPC token")

        try:
            for request in request_iterator:

                if request.HasField("run_cancel"):
                    logger.info(
                        "RunAssistant cancellation received run_id=%s reason=%s",
                        request.run_cancel.run_id,
                        request.run_cancel.reason,
                    )
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
                        run.pending_task_context_json, None
                    )

                    auth_context = {
                        "run_id": run.run_id,
                        "user_id": run.user_id,
                        "agency_id": run.agency_id,
                        "session_id": run.session_id,
                        "user_message": query,
                        "summary_memory": run.summary_memory or "",
                        "pending_task_context_json": json.dumps(pending_task_context),
                        "recent_messages_json": json.dumps(recent_messages or []),
                        "access_json": json.dumps(access or {}),
                    }

                    logger.info(
                        "RunAssistant run_start received run_id=%s user_id=%s agency_id=%s session_id=%s message=%r",
                        run.run_id,
                        run.user_id,
                        run.agency_id,
                        run.session_id,
                        query,
                    )

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
                        logger.info(
                            "RunAssistant progress event run_id=%s event_type=%s message=%r payload=%s",
                            run.run_id,
                            event.get("event_type"),
                            event.get("message"),
                            json.dumps(event.get("payload") or {}, default=str),
                        )
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
                            logger.exception(
                                "Assistant graph execution failed run_id=%s",
                                run.run_id,
                            )
                            event_queue.put(
                                {
                                    "event_type": AssistantEventType.RUN_FAILED.value,
                                    "message": "Unable to complete the request.",
                                    "payload": {
                                        "run_id": run.run_id,
                                        "stage": "graph_execution",
                                        "error": str(exc),
                                        "error_type": exc.__class__.__name__,
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
                            grpc_response_payload = {
                                "event_type": final_response.get("event_type"),
                                "message": final_response.get("message"),
                                "payload_json": final_response.get("payload_json"),
                                "summary_memory": final_response.get("summary_memory"),
                            }

                            logger.info(
                                "Sending final gRPC AssistantEvent run_id=%s event=%s",
                                run.run_id,
                                json.dumps(grpc_response_payload, default=str),
                            )

                            if not grpc_response_payload.get("event_type"):
                                logger.error(
                                    "Final response missing event_type run_id=%s final_response=%s result_keys=%s",
                                    run.run_id,
                                    json.dumps(final_response, default=str),
                                    list(result.keys()),
                                )
                                yield build_stream_event(
                                    event_type=AssistantEventType.RUN_FAILED.value,
                                    message="Unable to complete the request.",
                                    payload={
                                        "run_id": run.run_id,
                                        "stage": "final_response_validation",
                                        "error": "final_response.event_type is missing",
                                        "terminal": True,
                                    },
                                )
                                break

                            yield ai_runtime_pb2.AssistantStreamResponse(
                                event=ai_runtime_pb2.AssistantEvent(
                                    event_type=grpc_response_payload.get("event_type"),
                                    message=grpc_response_payload.get("message") or "",
                                    payload_json=grpc_response_payload.get(
                                        "payload_json"
                                    )
                                    or "{}",
                                    summary_memory=grpc_response_payload.get(
                                        "summary_memory"
                                    )
                                    or "",
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
        except Exception:
            logger.exception("RunAssistant stream failed before safe response could be sent")
            raise


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
