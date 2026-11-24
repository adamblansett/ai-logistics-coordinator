import json
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.db.base import ensure_utc, new_uuid, utcnow
from app.tracking.models import Shipment, TrackingEvent, TrackingException
from app.tracking.normalizer import NormalizedEvent
from app.tracking.schemas import (
    ShipmentCreate,
    ShipmentDetailRead,
    ShipmentRead,
    TrackingEventRead,
    TrackingExceptionRead,
)

_REASON_TO_EXCEPTION_TYPE: dict[str, str] = {
    "DETENTION": "DETENTION",
    "CUSTOMS_HOLD": "CUSTOMS_HOLD",
    "WEATHER": "WEATHER_DISRUPTION",
    "PORT_CONGESTION": "PORT_CONGESTION",
    "TEMP_EXCURSION": "TEMPERATURE_EXCURSION",
    "MECHANICAL": "MECHANICAL",
}


async def create_shipment(session: AsyncSession, payload: ShipmentCreate) -> Shipment:
    """Create and persist a tracked shipment with audit trail entry."""
    existing = await session.execute(
        select(Shipment).where(Shipment.reference_number == payload.reference_number.strip())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Shipment reference '{payload.reference_number}' already exists.",
        )

    sla_eta = ensure_utc(payload.sla_eta)
    current_eta = ensure_utc(payload.current_eta) if payload.current_eta else sla_eta
    delay_minutes = max(0, int((current_eta - sla_eta).total_seconds() // 60))
    now = utcnow()

    shipment = Shipment(
        id=new_uuid(),
        reference_number=payload.reference_number.strip(),
        bol_number=payload.bol_number.strip(),
        pro_number=payload.pro_number.strip(),
        carrier_scac=payload.carrier_scac.strip().upper(),
        carrier_name=payload.carrier_name.strip(),
        mode=payload.mode,
        origin=payload.origin.strip(),
        destination=payload.destination.strip(),
        last_location=(payload.last_location or payload.origin).strip(),
        status="DELAYED" if delay_minutes >= 60 else "PLANNED",
        sla_eta=sla_eta,
        current_eta=current_eta,
        delay_minutes=delay_minutes,
        weight_lbs=payload.weight_lbs,
        temperature_controlled=payload.temperature_controlled,
        created_at=now,
        updated_at=now,
    )
    session.add(shipment)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="shipment",
        entity_id=shipment.id,
        action="CREATED",
        actor=payload.actor,
        previous_state=None,
        new_state=shipment.status,
        details={
            "reference_number": shipment.reference_number,
            "bol_number": shipment.bol_number,
            "carrier_scac": shipment.carrier_scac,
        },
    )
    await session.commit()
    await session.refresh(shipment)
    return shipment


async def list_shipments(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
    search: str | None = None,
) -> list[Shipment]:
    """List shipments ordered by most recently updated."""
    stmt = select(Shipment).order_by(Shipment.updated_at.desc())
    if status_filter:
        stmt = stmt.where(Shipment.status == status_filter.strip().upper())
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Shipment.reference_number.ilike(pattern),
                Shipment.bol_number.ilike(pattern),
                Shipment.pro_number.ilike(pattern),
                Shipment.carrier_name.ilike(pattern),
                Shipment.origin.ilike(pattern),
                Shipment.destination.ilike(pattern),
            )
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_shipment_or_404(session: AsyncSession, shipment_id: str) -> Shipment:
    """Fetch a shipment by ID or raise HTTP 404."""
    result = await session.execute(select(Shipment).where(Shipment.id == shipment_id))
    shipment = result.scalar_one_or_none()
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{shipment_id}' not found.",
        )
    return shipment


async def get_shipment_detail(session: AsyncSession, shipment_id: str) -> ShipmentDetailRead:
    """Return shipment with chronological events and exceptions."""
    shipment = await get_shipment_or_404(session, shipment_id)
    events_res = await session.execute(
        select(TrackingEvent)
        .where(TrackingEvent.shipment_id == shipment.id)
        .order_by(TrackingEvent.event_timestamp.desc())
    )
    exc_res = await session.execute(
        select(TrackingException)
        .where(TrackingException.shipment_id == shipment.id)
        .order_by(TrackingException.detected_at.desc())
    )
    base = ShipmentRead.model_validate(shipment)
    return ShipmentDetailRead(
        **base.model_dump(),
        events=[TrackingEventRead.model_validate(e) for e in events_res.scalars().all()],
        exceptions=[TrackingExceptionRead.model_validate(ex) for ex in exc_res.scalars().all()],
    )


async def find_shipment_by_edi_identifiers(
    session: AsyncSession,
    *,
    bol_number: str | None,
    pro_number: str | None,
    reference_number: str | None,
) -> Shipment:
    """Resolve a shipment from EDI B10/L11 identifiers or raise HTTP 404."""
    filters = []
    if bol_number:
        filters.append(Shipment.bol_number == bol_number)
    if pro_number:
        filters.append(Shipment.pro_number == pro_number)
    if reference_number:
        filters.append(Shipment.reference_number == reference_number)

    if not filters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="EDI 214 payload must include a BOL, PRO, or reference identifier.",
        )

    result = await session.execute(select(Shipment).where(or_(*filters)).limit(1))
    shipment = result.scalar_one_or_none()
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No matching shipment found for BOL={bol_number}, "
                f"PRO={pro_number}, REF={reference_number}."
            ),
        )
    return shipment


def _determine_exception_details(
    shipment: Shipment,
    normalized: NormalizedEvent,
) -> tuple[str, str, str] | None:
    """Evaluate SLA slip and operational reason rules to determine exception tuple."""
    if normalized.normalized_status == "DELIVERED":
        return None

    reason = (normalized.reason_code or "").upper()
    exception_type: str | None = _REASON_TO_EXCEPTION_TYPE.get(reason)

    if exception_type is None and (
        shipment.delay_minutes >= 60 or normalized.normalized_status in {"DELAYED", "EXCEPTION"}
    ):
        exception_type = "ETA_SLIP"

    if exception_type is None:
        return None

    delay = shipment.delay_minutes
    if (
        exception_type == "TEMPERATURE_EXCURSION"
        or delay >= 720
        or (shipment.temperature_controlled and delay >= 180)
    ):
        severity = "CRITICAL"
    elif delay >= 240 or exception_type in {"CUSTOMS_HOLD", "PORT_CONGESTION"}:
        severity = "HIGH"
    elif delay >= 60 or exception_type in {"DETENTION", "WEATHER_DISRUPTION", "MECHANICAL"}:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    summary = (
        f"{exception_type} detected for {shipment.reference_number} at "
        f"{normalized.location} ({delay} min behind SLA ETA). {normalized.notes}".strip()
    )
    return exception_type, severity, summary


async def ingest_event(
    session: AsyncSession,
    shipment: Shipment,
    normalized: NormalizedEvent,
    *,
    raw_payload: dict[str, object],
    actor: str = "tracking-ingestor",
) -> tuple[TrackingEvent, Shipment, TrackingException | None]:
    """Persist a normalized tracking event, update shipment ETA/status, and detect exceptions."""
    prev_status = shipment.status
    now = utcnow()

    event = TrackingEvent(
        id=new_uuid(),
        shipment_id=shipment.id,
        source_format=normalized.source_format,
        raw_code=normalized.raw_code,
        normalized_status=normalized.normalized_status,
        reason_code=normalized.reason_code,
        location=normalized.location,
        event_timestamp=ensure_utc(normalized.event_timestamp),
        reported_eta=ensure_utc(normalized.reported_eta) if normalized.reported_eta else None,
        notes=normalized.notes,
        raw_payload=json.dumps(raw_payload, default=str),
        created_at=now,
    )
    session.add(event)

    shipment.last_location = normalized.location
    if normalized.reported_eta is not None:
        shipment.current_eta = ensure_utc(normalized.reported_eta)

    eta_diff = ensure_utc(shipment.current_eta) - ensure_utc(shipment.sla_eta)
    shipment.delay_minutes = max(0, int(eta_diff.total_seconds() // 60))

    if (
        normalized.normalized_status in {"DELAYED", "EXCEPTION"}
        and normalized.reported_eta is None
        and shipment.delay_minutes == 0
    ):
        # Quantify SLA slip when a delay/exception signal arrives without a new G62/ETA timestamp.
        shipment.current_eta = ensure_utc(shipment.sla_eta) + timedelta(minutes=180)
        shipment.delay_minutes = 180

    if normalized.normalized_status == "DELIVERED":
        shipment.status = "DELIVERED"
    elif normalized.normalized_status == "EXCEPTION":
        shipment.status = "EXCEPTION"
    elif shipment.delay_minutes >= 60 or normalized.normalized_status == "DELAYED":
        shipment.status = "DELAYED"
    else:
        shipment.status = normalized.normalized_status

    shipment.updated_at = now
    await session.flush()

    await record_audit_event(
        session,
        entity_type="shipment",
        entity_id=shipment.id,
        action="EVENT_INGESTED",
        actor=actor,
        previous_state=prev_status,
        new_state=shipment.status,
        details={
            "source_format": normalized.source_format,
            "raw_code": normalized.raw_code,
            "reason_code": normalized.reason_code,
            "location": normalized.location,
            "delay_minutes": shipment.delay_minutes,
        },
    )

    exception_record: TrackingException | None = None
    exc_info = _determine_exception_details(shipment, normalized)
    if exc_info is not None:
        exc_type, severity, summary = exc_info
        existing_res = await session.execute(
            select(TrackingException).where(
                TrackingException.shipment_id == shipment.id,
                TrackingException.exception_type == exc_type,
                TrackingException.status != "RESOLVED",
            )
        )
        exception_record = existing_res.scalar_one_or_none()
        if exception_record is None:
            exception_record = TrackingException(
                id=new_uuid(),
                shipment_id=shipment.id,
                exception_type=exc_type,
                severity=severity,
                status="OPEN",
                delay_minutes=shipment.delay_minutes,
                summary=summary,
                detected_at=now,
            )
            session.add(exception_record)
            await session.flush()
            await record_audit_event(
                session,
                entity_type="tracking_exception",
                entity_id=exception_record.id,
                action="EXCEPTION_OPENED",
                actor=actor,
                previous_state=None,
                new_state="OPEN",
                details={
                    "shipment_id": shipment.id,
                    "exception_type": exc_type,
                    "severity": severity,
                    "delay_minutes": shipment.delay_minutes,
                },
            )
        else:
            prev_exc_severity = exception_record.severity
            exception_record.severity = severity
            exception_record.delay_minutes = shipment.delay_minutes
            exception_record.summary = summary
            await session.flush()
            await record_audit_event(
                session,
                entity_type="tracking_exception",
                entity_id=exception_record.id,
                action="EXCEPTION_UPDATED",
                actor=actor,
                previous_state=prev_exc_severity,
                new_state=severity,
                details={
                    "shipment_id": shipment.id,
                    "exception_type": exc_type,
                    "delay_minutes": shipment.delay_minutes,
                },
            )

    await session.commit()
    await session.refresh(event)
    await session.refresh(shipment)
    if exception_record is not None:
        await session.refresh(exception_record)
    return event, shipment, exception_record


async def list_exceptions(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
    severity_filter: str | None = None,
) -> list[TrackingException]:
    """List tracking exceptions ordered by detection timestamp descending."""
    stmt = select(TrackingException).order_by(TrackingException.detected_at.desc())
    if status_filter:
        stmt = stmt.where(TrackingException.status == status_filter.strip().upper())
    if severity_filter:
        stmt = stmt.where(TrackingException.severity == severity_filter.strip().upper())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_exception_status(
    session: AsyncSession,
    exception_id: str,
    *,
    new_status: str,
    actor: str,
    resolution_notes: str | None,
) -> TrackingException:
    """Acknowledge or resolve a tracking exception with immutable audit record."""
    result = await session.execute(
        select(TrackingException).where(TrackingException.id == exception_id)
    )
    exc = result.scalar_one_or_none()
    if exc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tracking exception '{exception_id}' not found.",
        )

    prev_status = exc.status
    exc.status = new_status
    if resolution_notes is not None:
        exc.resolution_notes = resolution_notes.strip()
    if new_status == "RESOLVED":
        exc.resolved_at = utcnow()
    await session.flush()

    await record_audit_event(
        session,
        entity_type="tracking_exception",
        entity_id=exc.id,
        action="EXCEPTION_RESOLVED" if new_status == "RESOLVED" else "EXCEPTION_ACKNOWLEDGED",
        actor=actor,
        previous_state=prev_status,
        new_state=new_status,
        details={"shipment_id": exc.shipment_id, "resolution_notes": exc.resolution_notes},
    )
    await session.commit()
    await session.refresh(exc)
    return exc
