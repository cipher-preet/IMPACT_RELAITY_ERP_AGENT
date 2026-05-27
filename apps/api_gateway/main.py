from fastapi import FastAPI

from apps.api_gateway.routes.health import router as health_router
from apps.api_gateway.middleware.logging import log_requests
from apps.api_gateway.config.setting import settings

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.middleware("http")(log_requests)

app.include_router(health_router, prefix="/api/health", tags=["Health"])


@app.get("/")
async def root():
    return {"message": "AI Agent System Running"}
