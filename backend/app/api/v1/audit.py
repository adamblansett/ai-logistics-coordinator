import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import verify_audit_chain
from app.core.models import AuditLog
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogRead(BaseModel):
    id: str
    sequence_number: int
    entity_type: str
    entity_id: str
    action: str
    actor: str
    previous_state: str | None
    new_state: str | None
    details: dict[str, Any]
    prev_hash: str
    entry_hash: str
    created_at: datetime

    @classmethod
    def from_orm_model(cls, model: AuditLog) -> "AuditLogRead":
        return cls(
            id=model.id,
            sequence_number=model.sequence_number,
            entity_type=model.entity_type,
            entity_id=model.entity_id,
            action=model.action,
            actor=model.actor,
            previous_state=model.previous_state,
            new_state=model.new_state,
            details=json.loads(model.details_json or "{}"),
            prev_hash=model.prev_hash,
            entry_hash=model.entry_hash,
            created_at=model.created_at,
        )


class AuditVerifyResponse(BaseModel):
    valid: bool
    checked_entries: int
    first_broken_id: str | None


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs_endpoint(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AuditLogRead]:
    stmt = select(AuditLog).order_by(AuditLog.sequence_number.desc()).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type.strip())
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id.strip())
    if action:
        stmt = stmt.where(AuditLog.action == action.strip().upper())

    result = await session.execute(stmt)
    return [AuditLogRead.from_orm_model(entry) for entry in result.scalars().all()]


@router.get("/verify", response_model=AuditVerifyResponse)
async def verify_audit_chain_endpoint(
    session: AsyncSession = Depends(get_db),
) -> AuditVerifyResponse:
    valid, count, first_broken_id = await verify_audit_chain(session)
    return AuditVerifyResponse(
        valid=valid,
        checked_entries=count,
        first_broken_id=first_broken_id,
    )
