from apps.agent_runtime.grpc_runtime.generated import (
    ai_runtime_pb2,
    ai_runtime_pb2_grpc,
)

from apps.agent_runtime.grpc_runtime.runtime.runtime_manager import (
    runtime_manager,
)


class AIRuntimeService(
    ai_runtime_pb2_grpc.AIRuntimeServiceServicer
):

    async def ProcessQuery(
        self,
        request,
        context
    ):

        intent = (
            await runtime_manager
            .intent_classifier
            .classify(request.query)
        )

        return ai_runtime_pb2.QueryResponse(
            response=intent
        )