import json
from dataclasses import asdict
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.db.base import ensure_utc, new_uuid, utcnow
from app.llm.base import LLMRequest
from app.llm.router import LLMRouter
from app.memory.service import search_memories
from app.routing.models import CarrierLane, DisruptionAlert, RouteRecommendation
from app.routing.optimizer import evaluate_lanes
from app.routing.schemas import (
    CarrierLaneCreate,
    DisruptionAlertCreate,
    DisruptionAlertUpdate,
    RouteOptimizeRequest,
)
from app.tracking.models import Shipment


def _region_matches(left: str, right: str) -> bool:
    l_norm = left.strip().lower()
    r_norm = right.strip().lower()
    return l_norm == r_norm or l_norm in r_norm or r_norm in l_norm


async def list_lanes(
    session: AsyncSession,
    *,
    active_only: bool = False,
) -> list[CarrierLane]:
    stmt = select(CarrierLane).order_by(
        CarrierLane.origin_region.asc(),
        CarrierLane.base_rate_usd.asc(),
    )
    if active_only:
        stmt = stmt.where(CarrierLane.active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_lane(
    session: AsyncSession,
    payload: CarrierLaneCreate,
    *,
    actor_override: str | None = None,
) -> CarrierLane:
    lane = CarrierLane(
        id=new_uuid(),
        carrier_scac=payload.carrier_scac.strip().upper(),
        carrier_name=payload.carrier_name.strip(),
        origin_region=payload.origin_region.strip(),
        destination_region=payload.destination_region.strip(),
        mode=payload.mode,
        base_rate_usd=payload.base_rate_usd,
        fuel_surcharge_pct=payload.fuel_surcharge_pct,
        transit_hours=payload.transit_hours,
        on_time_rate=payload.on_time_rate,
        carbon_kg_per_ton_mile=payload.carbon_kg_per_ton_mile,
        supports_reefer=payload.supports_reefer,
        max_weight_lbs=payload.max_weight_lbs,
        disruption_risk_score=payload.disruption_risk_score,
        active=payload.active,
        created_at=utcnow(),
    )
    session.add(lane)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="carrier_lane",
        entity_id=lane.id,
        action="CREATED",
        actor=actor_override or payload.actor,
        previous_state=None,
        new_state="ACTIVE" if lane.active else "INACTIVE",
        details={
            "carrier_scac": lane.carrier_scac,
            "corridor": f"{lane.origin_region} -> {lane.destination_region}",
            "mode": lane.mode,
        },
    )
    await session.commit()
    await session.refresh(lane)
    return lane


async def list_disruptions(
    session: AsyncSession,
    *,
    active_only: bool = False,
) -> list[DisruptionAlert]:
    stmt = select(DisruptionAlert).order_by(DisruptionAlert.created_at.desc())
    if active_only:
        stmt = stmt.where(DisruptionAlert.active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_disruption(
    session: AsyncSession,
    payload: DisruptionAlertCreate,
    *,
    actor_override: str | None = None,
) -> DisruptionAlert:
    alert = DisruptionAlert(
        id=new_uuid(),
        region=payload.region.strip(),
        disruption_type=payload.disruption_type,
        severity=payload.severity,
        added_transit_hours=payload.added_transit_hours,
        cost_surcharge_pct=payload.cost_surcharge_pct,
        description=payload.description.strip(),
        active=payload.active,
        created_at=utcnow(),
    )
    session.add(alert)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="disruption_alert",
        entity_id=alert.id,
        action="CREATED",
        actor=actor_override or payload.actor,
        previous_state=None,
        new_state="ACTIVE" if alert.active else "INACTIVE",
        details={
            "region": alert.region,
            "disruption_type": alert.disruption_type,
            "severity": alert.severity,
        },
    )
    await session.commit()
    await session.refresh(alert)
    return alert


async def update_disruption(
    session: AsyncSession,
    disruption_id: str,
    payload: DisruptionAlertUpdate,
    *,
    actor_override: str | None = None,
) -> DisruptionAlert:
    result = await session.execute(
        select(DisruptionAlert).where(DisruptionAlert.id == disruption_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disruption alert '{disruption_id}' not found.",
        )

    prev_state = "ACTIVE" if alert.active else "INACTIVE"
    if payload.active is not None:
        alert.active = payload.active
    if payload.severity is not None:
        alert.severity = payload.severity
    if payload.added_transit_hours is not None:
        alert.added_transit_hours = payload.added_transit_hours
    if payload.cost_surcharge_pct is not None:
        alert.cost_surcharge_pct = payload.cost_surcharge_pct
    if payload.description is not None:
        alert.description = payload.description.strip()

    new_state = "ACTIVE" if alert.active else "INACTIVE"
    await session.flush()

    await record_audit_event(
        session,
        entity_type="disruption_alert",
        entity_id=alert.id,
        action="UPDATED",
        actor=actor_override or payload.actor,
        previous_state=prev_state,
        new_state=new_state,
        details={"region": alert.region, "severity": alert.severity},
    )
    await session.commit()
    await session.refresh(alert)
    return alert


async def optimize_route(
    session: AsyncSession,
    llm_router: LLMRouter,
    req: RouteOptimizeRequest,
    *,
    actor_override: str | None = None,
) -> RouteRecommendation:
    """Evaluate active lanes for a shipment or corridor and persist a reviewable recommendation."""
    shipment: Shipment | None = None
    if req.shipment_id:
        ship_res = await session.execute(select(Shipment).where(Shipment.id == req.shipment_id))
        shipment = ship_res.scalar_one_or_none()
        if shipment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shipment '{req.shipment_id}' not found.",
            )

    origin_region = (req.origin_region or (shipment.origin if shipment else "")).strip()
    destination_region = (
        req.destination_region or (shipment.destination if shipment else "")
    ).strip()
    if not origin_region or not destination_region:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide shipment_id or both origin_region and destination_region.",
        )

    weight_lbs = req.weight_lbs if req.weight_lbs is not None else (
        shipment.weight_lbs if shipment else 15000.0
    )
    temperature_controlled = (
        req.temperature_controlled
        if req.temperature_controlled is not None
        else (shipment.temperature_controlled if shipment else False)
    )

    all_lanes = await list_lanes(session, active_only=True)
    corridor_lanes = [
        lane
        for lane in all_lanes
        if _region_matches(lane.origin_region, origin_region)
        and _region_matches(lane.destination_region, destination_region)
    ]
    if not corridor_lanes:
        available = sorted({f"{ln.origin_region} -> {ln.destination_region}" for ln in all_lanes})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"No active carrier lanes found for corridor "
                f"'{origin_region} -> {destination_region}'. Available: {available}"
            ),
        )

    all_disruptions = await list_disruptions(session, active_only=True)
    corridor_disruptions = [
        d
        for d in all_disruptions
        if _region_matches(d.region, origin_region) or _region_matches(d.region, destination_region)
    ]

    scored = evaluate_lanes(
        corridor_lanes,
        corridor_disruptions,
        weight_lbs=weight_lbs,
        temperature_controlled=temperature_controlled,
        objective=req.objective,
        max_budget_usd=req.max_budget_usd,
        max_transit_hours=req.max_transit_hours,
    )
    if not scored:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No candidate carrier lanes satisfy the weight, reefer, budget, "
                "or transit-time constraints."
            ),
        )

    winner = scored[0]
    runner_up = asdict(scored[1]) if len(scored) > 1 else None
    disruption_labels = [
        f"{d.region}: {d.disruption_type} ({d.severity}, +{d.added_transit_hours}h)"
        for d in corridor_disruptions
    ]
    memory_hits = await search_memories(
        session,
        f"{origin_region} {destination_region} {req.objective} {winner.carrier_scac}",
        limit=2,
    )
    memory_titles = [
        f"{hit.memory.title} ({hit.score:.2f})" for hit in memory_hits
    ]

    llm_response = await llm_router.generate(
        LLMRequest(
            task_type="route_rationale",
            system_prompt=(
                "You are a senior freight network optimization specialist. "
                "Explain the selected carrier lane strictly using the supplied metrics."
            ),
            user_prompt=(
                f"Summarize why {winner.carrier_name} ({winner.carrier_scac}) was selected for "
                f"{origin_region} -> {destination_region} under objective {req.objective}."
            ),
            context={
                "origin_region": origin_region,
                "destination_region": destination_region,
                "objective": req.objective,
                "recommended_carrier_name": winner.carrier_name,
                "recommended_carrier_scac": winner.carrier_scac,
                "recommended_mode": winner.mode,
                "estimated_cost_usd": winner.estimated_cost_usd,
                "estimated_transit_hours": winner.estimated_transit_hours,
                "estimated_reliability": winner.estimated_reliability,
                "estimated_carbon_kg": winner.estimated_carbon_kg,
                "composite_score": winner.composite_score,
                "active_disruptions": disruption_labels,
                "historical_memories": memory_titles,
                "runner_up": runner_up,
            },
        )
    )

    rec = RouteRecommendation(
        id=new_uuid(),
        shipment_id=shipment.id if shipment else None,
        origin_region=origin_region,
        destination_region=destination_region,
        objective=req.objective,
        recommended_lane_id=winner.lane_id,
        recommended_carrier_scac=winner.carrier_scac,
        recommended_carrier_name=winner.carrier_name,
        recommended_mode=winner.mode,
        estimated_cost_usd=winner.estimated_cost_usd,
        estimated_transit_hours=winner.estimated_transit_hours,
        estimated_reliability=winner.estimated_reliability,
        estimated_carbon_kg=winner.estimated_carbon_kg,
        composite_score=winner.composite_score,
        alternatives_json=json.dumps([asdict(item) for item in scored]),
        rationale=llm_response.content,
        llm_provider=llm_response.provider,
        status="PENDING_REVIEW",
        created_at=utcnow(),
    )
    session.add(rec)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="route_recommendation",
        entity_id=rec.id,
        action="RECOMMENDATION_CREATED",
        actor=actor_override or req.actor,
        previous_state=None,
        new_state="PENDING_REVIEW",
        details={
            "shipment_id": rec.shipment_id,
            "objective": rec.objective,
            "carrier_scac": rec.recommended_carrier_scac,
            "composite_score": rec.composite_score,
        },
    )
    await session.commit()
    await session.refresh(rec)
    return rec


async def list_recommendations(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
) -> list[RouteRecommendation]:
    stmt = select(RouteRecommendation).order_by(RouteRecommendation.created_at.desc())
    if status_filter:
        stmt = stmt.where(RouteRecommendation.status == status_filter.strip().upper())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def decide_recommendation(
    session: AsyncSession,
    rec_id: str,
    *,
    decision: str,
    actor: str,
    notes: str | None,
) -> RouteRecommendation:
    """Approve or reject a pending route recommendation with dispatcher audit trail."""
    result = await session.execute(
        select(RouteRecommendation).where(RouteRecommendation.id == rec_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route recommendation '{rec_id}' not found.",
        )
    if rec.status != "PENDING_REVIEW":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recommendation is already '{rec.status}' and cannot be decided again.",
        )

    now = utcnow()
    rec.status = decision
    rec.reviewed_by = actor
    rec.review_notes = notes.strip() if notes else None
    rec.reviewed_at = now
    await session.flush()

    if decision == "APPROVED" and rec.shipment_id:
        ship_res = await session.execute(select(Shipment).where(Shipment.id == rec.shipment_id))
        shipment = ship_res.scalar_one_or_none()
        if shipment is not None:
            prev_carrier = shipment.carrier_scac
            shipment.carrier_scac = rec.recommended_carrier_scac
            shipment.carrier_name = rec.recommended_carrier_name
            shipment.mode = rec.recommended_mode
            shipment.current_eta = now + timedelta(hours=rec.estimated_transit_hours)
            shipment.delay_minutes = max(
                0,
                int((shipment.current_eta - ensure_utc(shipment.sla_eta)).total_seconds() // 60),
            )
            shipment.updated_at = now
            await session.flush()
            await record_audit_event(
                session,
                entity_type="shipment",
                entity_id=shipment.id,
                action="REROUTED",
                actor=actor,
                previous_state=prev_carrier,
                new_state=shipment.carrier_scac,
                details={
                    "recommendation_id": rec.id,
                    "new_carrier": shipment.carrier_name,
                    "new_eta": shipment.current_eta.isoformat(),
                },
            )

    await record_audit_event(
        session,
        entity_type="route_recommendation",
        entity_id=rec.id,
        action="APPROVED" if decision == "APPROVED" else "REJECTED",
        actor=actor,
        previous_state="PENDING_REVIEW",
        new_state=decision,
        details={"shipment_id": rec.shipment_id, "notes": rec.review_notes},
    )
    await session.commit()
    await session.refresh(rec)
    return rec
