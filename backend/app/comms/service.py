import json
from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comms.delivery import deliver_communication
from app.comms.models import CarrierCommunication
from app.comms.schemas import CommDraftRequest
from app.core.audit import record_audit_event
from app.core.config import Settings
from app.db.base import ensure_utc, new_uuid, utcnow
from app.inventory.models import InventoryAlert
from app.llm.base import LLMRequest
from app.llm.router import LLMRouter
from app.memory.service import search_memories
from app.tracking.models import Shipment, TrackingEvent, TrackingException


def _split_subject_and_body(
    raw_content: str,
    fallback_subject: str,
) -> tuple[str, str]:
    lines = raw_content.strip().splitlines()
    if lines and lines[0].upper().startswith("SUBJECT:"):
        subject = lines[0][8:].strip() or fallback_subject
        body_lines = lines[1:]
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        body = "\n".join(body_lines).strip() or raw_content.strip()
        return subject[:255], body
    return fallback_subject[:255], raw_content.strip()


async def draft_communication(
    session: AsyncSession,
    llm_router: LLMRouter,
    req: CommDraftRequest,
    *,
    actor_override: str | None = None,
) -> CarrierCommunication:
    """Generate a grounded carrier communication draft in PENDING_APPROVAL state."""
    ship_res = await session.execute(select(Shipment).where(Shipment.id == req.shipment_id))
    shipment = ship_res.scalar_one_or_none()
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{req.shipment_id}' not found.",
        )

    events_res = await session.execute(
        select(TrackingEvent)
        .where(TrackingEvent.shipment_id == shipment.id)
        .order_by(TrackingEvent.event_timestamp.desc())
        .limit(5)
    )
    recent_events = list(events_res.scalars().all())

    exc_res = await session.execute(
        select(TrackingException).where(
            TrackingException.shipment_id == shipment.id,
            TrackingException.status != "RESOLVED",
        )
    )
    open_exceptions = list(exc_res.scalars().all())

    alert_res = await session.execute(
        select(InventoryAlert).where(
            InventoryAlert.shipment_id == shipment.id,
            InventoryAlert.status != "RESOLVED",
        )
    )
    open_alerts = list(alert_res.scalars().all())

    memory_hits = await search_memories(
        session,
        f"{shipment.carrier_name} {shipment.origin} {shipment.destination} {req.comm_type}",
        limit=2,
    )

    grounding_facts: dict[str, Any] = {
        "comm_type": req.comm_type,
        "channel": req.channel,
        "shipment_id": shipment.id,
        "reference_number": shipment.reference_number,
        "bol_number": shipment.bol_number,
        "pro_number": shipment.pro_number,
        "carrier_scac": shipment.carrier_scac,
        "carrier_name": shipment.carrier_name,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "last_location": shipment.last_location,
        "status": shipment.status,
        "sla_eta": ensure_utc(shipment.sla_eta).strftime("%Y-%m-%d %H:%M UTC"),
        "current_eta": ensure_utc(shipment.current_eta).strftime("%Y-%m-%d %H:%M UTC"),
        "delay_minutes": shipment.delay_minutes,
        "recipient_name": req.recipient_name.strip(),
        "recent_events": [
            f"{ev.normalized_status} at {ev.location} ({ev.raw_code})" for ev in recent_events
        ],
        "open_exceptions": [
            f"{ex.exception_type} [{ex.severity}] - {ex.delay_minutes}m delay"
            for ex in open_exceptions
        ],
        "open_inventory_alerts": [
            f"{al.sku} {al.alert_type} ({al.variance_qty} units, ${al.financial_impact_usd:,.2f})"
            for al in open_alerts
        ],
        "historical_context": [
            f"{hit.memory.title}: {hit.memory.content}" for hit in memory_hits
        ],
        "custom_notes": req.custom_notes.strip(),
    }

    llm_response = await llm_router.generate(
        LLMRequest(
            task_type="carrier_comm",
            system_prompt=(
                "You are an AI logistics coordinator drafting an operational carrier message. "
                "Output 'SUBJECT: <subject>' on the first line followed by the message body. "
                "Cite only verified grounding facts."
            ),
            user_prompt=(
                f"Draft a {req.comm_type} via {req.channel} to {req.recipient_name} "
                f"({req.recipient_contact}) for shipment {shipment.reference_number} "
                f"(BOL {shipment.bol_number}, PRO {shipment.pro_number}). "
                f"Notes: {req.custom_notes.strip() or 'None'}."
            ),
            context=grounding_facts,
        )
    )

    fallback_subject = (
        f"{req.comm_type.replace('_', ' ').title()} — "
        f"Load {shipment.reference_number} (BOL {shipment.bol_number})"
    )
    subject, body = _split_subject_and_body(llm_response.content, fallback_subject)

    comm = CarrierCommunication(
        id=new_uuid(),
        shipment_id=shipment.id,
        comm_type=req.comm_type,
        channel=req.channel,
        recipient_name=req.recipient_name.strip(),
        recipient_contact=req.recipient_contact.strip(),
        subject=subject,
        body=body,
        grounding_facts_json=json.dumps(grounding_facts, default=str),
        llm_provider=llm_response.provider,
        llm_model=llm_response.model,
        pii_redacted=llm_response.pii_redacted,
        redacted_categories_json=json.dumps(llm_response.redacted_categories),
        status="PENDING_APPROVAL",
        created_by=actor_override or req.actor,
        created_at=utcnow(),
    )
    session.add(comm)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="carrier_comm",
        entity_id=comm.id,
        action="DRAFT_CREATED",
        actor=actor_override or req.actor,
        previous_state=None,
        new_state="PENDING_APPROVAL",
        details={
            "shipment_id": shipment.id,
            "comm_type": comm.comm_type,
            "channel": comm.channel,
            "llm_provider": comm.llm_provider,
            "pii_redacted": comm.pii_redacted,
        },
    )
    await session.commit()
    await session.refresh(comm)
    return comm


async def list_communications(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
    shipment_id: str | None = None,
) -> list[CarrierCommunication]:
    stmt = select(CarrierCommunication).order_by(CarrierCommunication.created_at.desc())
    if status_filter:
        stmt = stmt.where(CarrierCommunication.status == status_filter.strip().upper())
    if shipment_id:
        stmt = stmt.where(CarrierCommunication.shipment_id == shipment_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_communication_or_404(
    session: AsyncSession,
    comm_id: str,
) -> CarrierCommunication:
    result = await session.execute(
        select(CarrierCommunication).where(CarrierCommunication.id == comm_id)
    )
    comm = result.scalar_one_or_none()
    if comm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier communication '{comm_id}' not found.",
        )
    return comm


async def update_draft(
    session: AsyncSession,
    comm_id: str,
    *,
    subject: str | None,
    body: str | None,
    actor: str,
) -> CarrierCommunication:
    """Allow dispatcher edits only while draft is awaiting sign-off."""
    comm = await get_communication_or_404(session, comm_id)
    if comm.status not in {"DRAFT", "PENDING_APPROVAL"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit communication in state '{comm.status}'.",
        )

    if subject is not None:
        comm.subject = subject.strip()
    if body is not None:
        comm.body = body.strip()
    await session.flush()

    await record_audit_event(
        session,
        entity_type="carrier_comm",
        entity_id=comm.id,
        action="DRAFT_EDITED",
        actor=actor,
        previous_state=comm.status,
        new_state=comm.status,
        details={"subject_updated": subject is not None, "body_updated": body is not None},
    )
    await session.commit()
    await session.refresh(comm)
    return comm


async def decide_communication(
    session: AsyncSession,
    comm_id: str,
    *,
    decision: str,
    actor: str,
    notes: str | None,
) -> CarrierCommunication:
    """Approve or reject a pending carrier communication."""
    comm = await get_communication_or_404(session, comm_id)
    if comm.status not in {"DRAFT", "PENDING_APPROVAL"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Communication is in state '{comm.status}' and cannot be decided.",
        )

    prev_status = comm.status
    comm.status = decision
    comm.reviewed_by = actor
    comm.review_notes = notes.strip() if notes else None
    comm.reviewed_at = utcnow()
    await session.flush()

    await record_audit_event(
        session,
        entity_type="carrier_comm",
        entity_id=comm.id,
        action="APPROVED" if decision == "APPROVED" else "REJECTED",
        actor=actor,
        previous_state=prev_status,
        new_state=decision,
        details={"shipment_id": comm.shipment_id, "notes": comm.review_notes},
    )
    await session.commit()
    await session.refresh(comm)
    return comm


async def send_communication(
    session: AsyncSession,
    comm_id: str,
    *,
    actor: str,
    settings: Settings | None = None,
) -> CarrierCommunication:
    """Dispatch an APPROVED communication; strictly rejects any unapproved state."""
    comm = await get_communication_or_404(session, comm_id)
    if comm.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Communication must be APPROVED by a dispatcher before sending. "
                f"Current status: '{comm.status}'."
            ),
        )

    effective_settings = settings or Settings()
    try:
        receipt = await deliver_communication(comm, effective_settings)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    comm.status = "SENT"
    comm.sent_at = utcnow()
    comm.external_message_id = receipt.external_message_id
    comm.delivery_attempts = receipt.attempts
    comm.delivery_receipt_json = json.dumps(asdict(receipt))
    await session.flush()

    await record_audit_event(
        session,
        entity_type="carrier_comm",
        entity_id=comm.id,
        action="SENT",
        actor=actor,
        previous_state="APPROVED",
        new_state="SENT",
        details={
            "channel": comm.channel,
            "recipient_contact": comm.recipient_contact,
            "external_message_id": comm.external_message_id,
            "delivery_mode": receipt.delivery_mode,
            "delivery_attempts": receipt.attempts,
        },
    )
    await session.commit()
    await session.refresh(comm)
    return comm
