from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.agent_runtime.runtime.runtime_manager import RuntimeManager

from apps.api_gateway.routes.health import (
    router as health_router,
)

from apps.api_gateway.routes.Test import (
    router as test_router,
)

from apps.api_gateway.middleware.logging import (
    log_requests,
)

from apps.api_gateway.config.setting import (
    settings,
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    runtime_manager = RuntimeManager()
    print("Initializing Runtime Manager...")
    
    await runtime_manager.initialize()
    app.state.runtime_manager = runtime_manager
    yield
    await runtime_manager.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.middleware("http")(log_requests)

app.include_router(
    health_router,
    prefix="/api/health",
    tags=["Health"],
)

app.include_router(
    test_router,
    prefix="/api/test",
    tags=["AI Testing"],
)


@app.get("/")
async def root():

    return {"message": "AI Agent System Running"}
