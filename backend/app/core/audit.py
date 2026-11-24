import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import AuditLog
from app.db.base import new_uuid, utcnow


def compute_entry_hash(
    *,
    sequence_number: int,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    previous_state: str | None,
    new_state: str | None,
    details_json: str,
    prev_hash: str,
) -> str:
    """Compute a deterministic SHA-256 digest over canonical audit record fields."""
    payload = json.dumps(
        {
            "sequence_number": sequence_number,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": actor,
            "previous_state": previous_state,
            "new_state": new_state,
            "details_json": details_json,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def record_audit_event(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str = "system",
    previous_state: str | None = None,
    new_state: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Append a tamper-evident hash-chained entry to the audit log."""
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.sequence_number.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()
    next_seq = (latest.sequence_number + 1) if latest is not None else 1
    prev_hash = latest.entry_hash if latest is not None else "GENESIS"
    details_json = json.dumps(details or {}, sort_keys=True, default=str)

    entry_hash = compute_entry_hash(
        sequence_number=next_seq,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        previous_state=previous_state,
        new_state=new_state,
        details_json=details_json,
        prev_hash=prev_hash,
    )

    entry = AuditLog(
        id=new_uuid(),
        sequence_number=next_seq,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        previous_state=previous_state,
        new_state=new_state,
        details_json=details_json,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=utcnow(),
    )
    session.add(entry)
    await session.flush()
    return entry


async def verify_audit_chain(session: AsyncSession) -> tuple[bool, int, str | None]:
    """Verify full SHA-256 hash chain continuity across all audit_logs rows."""
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.sequence_number.asc())
    )
    entries = list(result.scalars().all())
    expected_prev_hash = "GENESIS"
    expected_seq = 1

    for entry in entries:
        if entry.sequence_number != expected_seq or entry.prev_hash != expected_prev_hash:
            return False, len(entries), entry.id

        recomputed = compute_entry_hash(
            sequence_number=entry.sequence_number,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            action=entry.action,
            actor=entry.actor,
            previous_state=entry.previous_state,
            new_state=entry.new_state,
            details_json=entry.details_json,
            prev_hash=entry.prev_hash,
        )
        if recomputed != entry.entry_hash:
            return False, len(entries), entry.id

        expected_prev_hash = entry.entry_hash
        expected_seq += 1

    return True, len(entries), None
