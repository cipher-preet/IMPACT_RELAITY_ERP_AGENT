from concurrent import futures
import grpc

from apps.agent_runtime.grpc_runtime.generated import (
    ai_runtime_pb2,
    ai_runtime_pb2_grpc,
)


class AIRuntimeService(ai_runtime_pb2_grpc.AIRuntimeServiceServicer):

    def ProcessQuery(self, request, context):

        print("Role:", request.auth.role)


        return ai_runtime_pb2.AIQueryResponse(
            success=True, response=f"AI processed: {request.query}"
        )


def start_grpc_server():

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    ai_runtime_pb2_grpc.add_AIRuntimeServiceServicer_to_server(
        AIRuntimeService(), server
    )

    server.add_insecure_port("[::]:50051")

    print("\n gRPC Server Running On Port 50051\n")

    server.start()

    server.wait_for_termination()


if __name__ == "__main__":

    start_grpc_server()
