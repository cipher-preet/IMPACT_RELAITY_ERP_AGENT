from fastapi import APIRouter
from src.controllers.health_controller import health_check

router = APIRouter()


@router.get("/")
async def health():
    return health_check()