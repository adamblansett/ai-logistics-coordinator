from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, require_roles, resolve_actor
from app.core.config import Settings, get_runtime_settings
from app.db.session import get_db
from app.workers.tasks import (
    ingest_edi214_batch_task,
    run_edi214_batch,
    run_sla_breach_sweep,
    sweep_sla_breaches_task,
)

router = APIRouter(prefix="/workers", tags=["workers"])


class EdiBatchRequest(BaseModel):
    payloads: list[str] = Field(min_length=1, max_length=100)
    actor: str = Field(default="edi-batch-api", max_length=128)


class WorkerDispatchResponse(BaseModel):
    execution_mode: str
    queued: bool
    task_id: str | None = None
    summary: dict[str, Any]


@router.post("/sla-sweep", response_model=WorkerDispatchResponse)
async def trigger_sla_sweep_endpoint(
    principal: Principal = Depends(require_roles("DISPATCHER")),
    settings: Settings = Depends(get_runtime_settings),
    session: AsyncSession = Depends(get_db),
) -> WorkerDispatchResponse:
    """Trigger an SLA breach sweep inline or via Celery worker queue."""
    if settings.task_execution_mode == "celery":
        async_result = sweep_sla_breaches_task.delay()
        return WorkerDispatchResponse(
            execution_mode="celery",
            queued=True,
            task_id=str(async_result.id),
            summary={"status": "queued"},
        )

    actor = resolve_actor(principal, "sla-sweep-api")
    summary = await run_sla_breach_sweep(session, actor=actor)
    return WorkerDispatchResponse(
        execution_mode="inline",
        queued=False,
        summary=summary,
    )


@router.post("/edi214-batch", response_model=WorkerDispatchResponse)
async def trigger_edi214_batch_endpoint(
    payload: EdiBatchRequest,
    principal: Principal = Depends(require_roles("WEBHOOK_INGESTOR", "DISPATCHER")),
    settings: Settings = Depends(get_runtime_settings),
    session: AsyncSession = Depends(get_db),
) -> WorkerDispatchResponse:
    """Ingest a batch of raw X12 EDI 214 messages inline or via Celery worker queue."""
    actor = resolve_actor(principal, payload.actor)
    if settings.task_execution_mode == "celery":
        async_result = ingest_edi214_batch_task.delay(payload.payloads, actor)
        return WorkerDispatchResponse(
            execution_mode="celery",
            queued=True,
            task_id=str(async_result.id),
            summary={"total": len(payload.payloads), "status": "queued"},
        )

    summary = await run_edi214_batch(session, payload.payloads, actor=actor)
    return WorkerDispatchResponse(
        execution_mode="inline",
        queued=False,
        summary=summary,
    )
