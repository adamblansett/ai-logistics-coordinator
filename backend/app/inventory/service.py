import json
from dataclasses import asdict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.db.base import new_uuid, utcnow
from app.inventory.models import InventoryAlert, InventoryReconciliation
from app.inventory.reconciler import reconcile_counts
from app.inventory.schemas import (
    InventoryAlertRead,
    InventoryReconciliationDetailRead,
    InventoryReconciliationRead,
    ReconciliationCreate,
)
from app.llm.base import LLMRequest
from app.llm.router import LLMRouter
from app.tracking.models import Shipment


async def run_reconciliation(
    session: AsyncSession,
    llm_router: LLMRouter,
    req: ReconciliationCreate,
) -> InventoryReconciliation:
    """Reconcile expected ASN/BOL quantities with received counts and persist alerts."""
    if req.shipment_id:
        ship_res = await session.execute(select(Shipment).where(Shipment.id == req.shipment_id))
        if ship_res.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shipment '{req.shipment_id}' not found.",
            )

    result = reconcile_counts(req.expected_lines, req.received_lines)
    issue_dicts = [asdict(item) for item in result.issues]

    llm_response = await llm_router.generate(
        LLMRequest(
            task_type="inventory_discrepancy",
            system_prompt=(
                "You are a warehouse inventory audit specialist. "
                "Summarize receiving reconciliation variances using only verified metrics."
            ),
            user_prompt=(
                f"Summarize ASN {req.asn_number} / BOL {req.bol_number} receiving at "
                f"warehouse {req.warehouse_code}."
            ),
            context={
                "asn_number": req.asn_number,
                "bol_number": req.bol_number,
                "warehouse_code": req.warehouse_code,
                "expected_total_units": result.expected_total_units,
                "received_total_units": result.received_total_units,
                "damaged_total_units": result.damaged_total_units,
                "variance_units": result.variance_units,
                "shrinkage_pct": result.shrinkage_pct,
                "financial_impact_usd": result.financial_impact_usd,
                "issues": issue_dicts,
            },
        )
    )

    rec_status = "MATCHED" if not result.issues else "DISCREPANCY_OPEN"
    now = utcnow()
    rec = InventoryReconciliation(
        id=new_uuid(),
        shipment_id=req.shipment_id,
        asn_number=req.asn_number.strip(),
        bol_number=req.bol_number.strip(),
        warehouse_code=req.warehouse_code.strip().upper(),
        expected_total_units=result.expected_total_units,
        received_total_units=result.received_total_units,
        damaged_total_units=result.damaged_total_units,
        variance_units=result.variance_units,
        shrinkage_pct=result.shrinkage_pct,
        financial_impact_usd=result.financial_impact_usd,
        status=rec_status,
        discrepancies_json=json.dumps(issue_dicts),
        ai_summary=llm_response.content,
        llm_provider=llm_response.provider,
        reconciled_by=req.actor,
        created_at=now,
    )
    session.add(rec)
    await session.flush()

    for finding in result.issues:
        alert = InventoryAlert(
            id=new_uuid(),
            reconciliation_id=rec.id,
            shipment_id=req.shipment_id,
            sku=finding.sku,
            description=finding.description,
            alert_type=finding.alert_type,
            severity=finding.severity,
            expected_qty=finding.expected_qty,
            received_qty=finding.received_qty,
            damaged_qty=finding.damaged_qty,
            variance_qty=finding.variance_qty,
            financial_impact_usd=finding.financial_impact_usd,
            status="OPEN",
            created_at=now,
        )
        session.add(alert)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="inventory_reconciliation",
        entity_id=rec.id,
        action="RECONCILED",
        actor=req.actor,
        previous_state=None,
        new_state=rec_status,
        details={
            "asn_number": rec.asn_number,
            "bol_number": rec.bol_number,
            "warehouse_code": rec.warehouse_code,
            "variance_units": rec.variance_units,
            "financial_impact_usd": rec.financial_impact_usd,
            "alert_count": len(result.issues),
        },
    )
    await session.commit()
    await session.refresh(rec)
    return rec


async def list_reconciliations(session: AsyncSession) -> list[InventoryReconciliation]:
    result = await session.execute(
        select(InventoryReconciliation).order_by(InventoryReconciliation.created_at.desc())
    )
    return list(result.scalars().all())


async def get_reconciliation_detail(
    session: AsyncSession,
    rec_id: str,
) -> InventoryReconciliationDetailRead:
    rec_res = await session.execute(
        select(InventoryReconciliation).where(InventoryReconciliation.id == rec_id)
    )
    rec = rec_res.scalar_one_or_none()
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory reconciliation '{rec_id}' not found.",
        )

    alerts_res = await session.execute(
        select(InventoryAlert)
        .where(InventoryAlert.reconciliation_id == rec.id)
        .order_by(InventoryAlert.financial_impact_usd.desc())
    )
    base = InventoryReconciliationRead.from_orm_model(rec)
    return InventoryReconciliationDetailRead(
        **base.model_dump(),
        alerts=[InventoryAlertRead.model_validate(item) for item in alerts_res.scalars().all()],
    )


async def list_alerts(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
    severity_filter: str | None = None,
) -> list[InventoryAlert]:
    stmt = select(InventoryAlert).order_by(InventoryAlert.created_at.desc())
    if status_filter:
        stmt = stmt.where(InventoryAlert.status == status_filter.strip().upper())
    if severity_filter:
        stmt = stmt.where(InventoryAlert.severity == severity_filter.strip().upper())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_alert(
    session: AsyncSession,
    alert_id: str,
    *,
    new_status: str,
    actor: str,
    resolution_notes: str | None,
) -> InventoryAlert:
    """Update an inventory discrepancy alert and resolve parent reconciliation when complete."""
    result = await session.execute(select(InventoryAlert).where(InventoryAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory alert '{alert_id}' not found.",
        )

    prev_status = alert.status
    alert.status = new_status
    if resolution_notes is not None:
        alert.resolution_notes = resolution_notes.strip()
    if new_status == "RESOLVED":
        alert.resolved_at = utcnow()
    await session.flush()

    await record_audit_event(
        session,
        entity_type="inventory_alert",
        entity_id=alert.id,
        action="ALERT_UPDATED",
        actor=actor,
        previous_state=prev_status,
        new_state=new_status,
        details={
            "reconciliation_id": alert.reconciliation_id,
            "sku": alert.sku,
            "resolution_notes": alert.resolution_notes,
        },
    )

    if new_status == "RESOLVED":
        sibling_res = await session.execute(
            select(InventoryAlert.id)
            .where(
                InventoryAlert.reconciliation_id == alert.reconciliation_id,
                InventoryAlert.status != "RESOLVED",
            )
            .limit(1)
        )
        if sibling_res.scalar_one_or_none() is None:
            parent_res = await session.execute(
                select(InventoryReconciliation).where(
                    InventoryReconciliation.id == alert.reconciliation_id
                )
            )
            parent = parent_res.scalar_one_or_none()
            if parent is not None and parent.status != "RESOLVED":
                prev_parent_status = parent.status
                parent.status = "RESOLVED"
                await session.flush()
                await record_audit_event(
                    session,
                    entity_type="inventory_reconciliation",
                    entity_id=parent.id,
                    action="RECONCILIATION_RESOLVED",
                    actor=actor,
                    previous_state=prev_parent_status,
                    new_state="RESOLVED",
                    details={"asn_number": parent.asn_number},
                )

    await session.commit()
    await session.refresh(alert)
    return alert
