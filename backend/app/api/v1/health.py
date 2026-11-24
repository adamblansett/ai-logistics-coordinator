from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_runtime_settings
from app.db.session import ensure_db_initialized

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    app_name: str
    version: str
    environment: str
    llm_provider: str
    database: str = "ok"


@router.get("", response_model=HealthResponse)
@router.get("/live", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_runtime_settings)) -> HealthResponse:
    """Return service liveness and runtime configuration summary."""
    return HealthResponse(
        status="ok",
        service=settings.app_slug,
        app_name=settings.app_name,
        version="0.1.0",
        environment=settings.app_env,
        llm_provider=settings.llm_default_provider,
        database="ok",
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check(
    request: Request,
    settings: Settings = Depends(get_runtime_settings),
) -> HealthResponse:
    """Verify database readiness and return service configuration summary."""
    try:
        await ensure_db_initialized(request.app)
        session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database readiness check failed: {exc}",
        ) from exc

    return HealthResponse(
        status="ok",
        service=settings.app_slug,
        app_name=settings.app_name,
        version="0.1.0",
        environment=settings.app_env,
        llm_provider=settings.llm_default_provider,
        database="ok",
    )
