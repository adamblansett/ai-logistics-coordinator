import asyncio
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.config import get_settings
from app.db.base import ensure_utc, new_uuid, utcnow
from app.db.session import create_engine_and_sessionmaker
from app.tracking.models import Shipment, TrackingException
from app.tracking.normalizer import parse_edi_214
from app.tracking.service import find_shipment_by_edi_identifiers, ingest_event
from app.workers.celery_app import celery_app


def _sla_severity(shipment: Shipment, delay_minutes: int) -> str:
    if delay_minutes >= 720 or (shipment.temperature_controlled and delay_minutes >= 180):
        return "CRITICAL"
    if delay_minutes >= 240:
        return "HIGH"
    if delay_minutes >= 60:
        return "MEDIUM"
    return "LOW"


async def run_sla_breach_sweep(
    session: AsyncSession,
    *,
    actor: str = "sla-worker",
) -> dict[str, Any]:
    """Scan active shipments for overdue SLA ETAs and open or escalate ETA_SLIP exceptions."""
    now = utcnow()
    rows = list(
        (await session.execute(select(Shipment).where(Shipment.status != "DELIVERED")))
        .scalars()
        .all()
    )

    breached_shipments = 0
    exceptions_opened_or_updated = 0

    for shipment in rows:
        sla_eta = ensure_utc(shipment.sla_eta)
        current_eta = ensure_utc(shipment.current_eta)
        overdue_minutes = max(0, int((now - sla_eta).total_seconds() // 60))
        effective_delay = max(
            shipment.delay_minutes,
            overdue_minutes,
            max(0, int((current_eta - sla_eta).total_seconds() // 60)),
        )
        is_breached = now > sla_eta or effective_delay >= 60
        if not is_breached:
            continue

        breached_shipments += 1
        prev_status = shipment.status
        if now > current_eta:
            shipment.current_eta = now
        shipment.delay_minutes = effective_delay
        if shipment.status not in {"DELAYED", "EXCEPTION"}:
            shipment.status = "DELAYED"
        shipment.updated_at = now
        await session.flush()

        existing_exc = (
            await session.execute(
                select(TrackingException)
                .where(
                    TrackingException.shipment_id == shipment.id,
                    TrackingException.exception_type == "ETA_SLIP",
                    TrackingException.status != "RESOLVED",
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        severity = _sla_severity(shipment, effective_delay)
        summary = (
            f"SLA breach sweep flagged {shipment.reference_number} "
            f"({effective_delay} min past SLA ETA) at {shipment.last_location}."
        )

        if existing_exc is None:
            exc = TrackingException(
                id=new_uuid(),
                shipment_id=shipment.id,
                exception_type="ETA_SLIP",
                severity=severity,
                status="OPEN",
                delay_minutes=effective_delay,
                summary=summary,
                detected_at=now,
            )
            session.add(exc)
            await session.flush()
            exceptions_opened_or_updated += 1
            await record_audit_event(
                session,
                entity_type="tracking_exception",
                entity_id=exc.id,
                action="SLA_SWEEP_OPENED",
                actor=actor,
                previous_state=prev_status,
                new_state="OPEN",
                details={
                    "shipment_id": shipment.id,
                    "delay_minutes": effective_delay,
                    "severity": severity,
                },
            )
        elif (
            existing_exc.delay_minutes != effective_delay
            or existing_exc.severity != severity
        ):
            prev_sev = existing_exc.severity
            existing_exc.delay_minutes = effective_delay
            existing_exc.severity = severity
            existing_exc.summary = summary
            await session.flush()
            exceptions_opened_or_updated += 1
            await record_audit_event(
                session,
                entity_type="tracking_exception",
                entity_id=existing_exc.id,
                action="SLA_SWEEP_ESCALATED",
                actor=actor,
                previous_state=prev_sev,
                new_state=severity,
                details={
                    "shipment_id": shipment.id,
                    "delay_minutes": effective_delay,
                },
            )

    await record_audit_event(
        session,
        entity_type="system",
        entity_id="sla-sweep",
        action="SLA_SWEEP_COMPLETED",
        actor=actor,
        previous_state=None,
        new_state="COMPLETED",
        details={
            "checked_shipments": len(rows),
            "breached_shipments": breached_shipments,
            "exceptions_opened_or_updated": exceptions_opened_or_updated,
        },
    )
    await session.commit()
    return {
        "checked_shipments": len(rows),
        "breached_shipments": breached_shipments,
        "exceptions_opened_or_updated": exceptions_opened_or_updated,
    }


async def run_edi214_batch(
    session: AsyncSession,
    payloads: list[str],
    *,
    actor: str = "edi-batch-worker",
) -> dict[str, Any]:
    """Parse and ingest a batch of raw X12 EDI 214 messages without aborting on bad items."""
    succeeded = 0
    failed = 0
    results: list[dict[str, Any]] = []

    for index, raw_edi in enumerate(payloads):
        try:
            normalized = parse_edi_214(raw_edi)
            shipment = await find_shipment_by_edi_identifiers(
                session,
                bol_number=normalized.bol_number,
                pro_number=normalized.pro_number,
                reference_number=normalized.reference_number,
            )
            event, updated_shipment, exc = await ingest_event(
                session,
                shipment,
                normalized,
                raw_payload={"raw_edi_214": raw_edi, "batch_index": index},
                actor=actor,
            )
            succeeded += 1
            results.append(
                {
                    "index": index,
                    "ok": True,
                    "shipment_id": updated_shipment.id,
                    "reference_number": updated_shipment.reference_number,
                    "event_id": event.id,
                    "exception_id": exc.id if exc else None,
                }
            )
        except (ValueError, HTTPException) as exc_err:
            failed += 1
            detail = exc_err.detail if isinstance(exc_err, HTTPException) else str(exc_err)
            results.append({"index": index, "ok": False, "error": str(detail)})

    return {
        "total": len(payloads),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


async def _run_sla_sweep_standalone() -> dict[str, Any]:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    try:
        async with session_factory() as session:
            return await run_sla_breach_sweep(session, actor="celery-sla-worker")
    finally:
        await engine.dispose()


async def _run_edi_batch_standalone(payloads: list[str], actor: str) -> dict[str, Any]:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    try:
        async with session_factory() as session:
            return await run_edi214_batch(session, payloads, actor=actor)
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.sweep_sla_breaches_task")
def sweep_sla_breaches_task() -> dict[str, Any]:
    """Celery task entrypoint for periodic SLA breach sweeps."""
    return asyncio.run(_run_sla_sweep_standalone())


@celery_app.task(name="app.workers.tasks.ingest_edi214_batch_task")
def ingest_edi214_batch_task(
    payloads: list[str],
    actor: str = "celery-edi-worker",
) -> dict[str, Any]:
    """Celery task entrypoint for asynchronous bulk EDI 214 ingestion."""
    return asyncio.run(_run_edi_batch_standalone(payloads, actor))
