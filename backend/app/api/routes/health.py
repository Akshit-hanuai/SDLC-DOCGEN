from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.api import HealthResponse
from app.services.llm.client import get_llm_client, probe_vllm

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    status: dict = {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "database": "unknown",
        "llm": {"mode": settings.llm_mode},
    }
    try:
        await db.execute(text("SELECT 1"))
        status["database"] = "reachable"
    except Exception as e:  # noqa: BLE001 - endpoint reports degraded state instead of raising
        status["database"] = "unreachable"
        status["status"] = "degraded"
        status["error"] = str(e)

    try:
        client = get_llm_client()
        status["llm"]["client"] = client.name if client else None
        status["llm"]["model"] = settings.llm_model
        if settings.llm_mode != "mock":
            status["llm"]["endpoint_reachable"] = probe_vllm()
    except Exception as e:  # noqa: BLE001
        status["llm"]["client"] = "unavailable"
        status["llm"]["endpoint_reachable"] = False
        status["llm"]["error"] = str(e)

    return status