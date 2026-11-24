from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.audit import AuditLogRead
from app.comms.models import CarrierCommunication
from app.core.models import AuditLog
from app.db.session import get_db
from app.inventory.models import InventoryAlert
from app.routing.models import DisruptionAlert, RouteRecommendation
from app.tracking.models import Shipment, TrackingException

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummaryResponse(BaseModel):
    total_shipments: int
    delayed_shipments: int
    open_tracking_exceptions: int
    critical_exceptions: int
    active_disruptions: int
    pending_route_recommendations: int
    pending_comm_approvals: int
    sent_comms: int
    open_inventory_alerts: int
    inventory_exposure_usd: float
    total_audit_entries: int
    recent_audit_logs: list[AuditLogRead]


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    session: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Aggregate live operational KPIs across tracking, routing, comms, inventory, and audit."""
    total_shipments = int(
        (await session.execute(select(func.count(Shipment.id)))).scalar_one() or 0
    )
    delayed_shipments = int(
        (
            await session.execute(
                select(func.count(Shipment.id)).where(
                    Shipment.status != "DELIVERED",
                    or_(
                        Shipment.status.in_(["DELAYED", "EXCEPTION"]),
                        Shipment.delay_minutes >= 60,
                    ),
                )
            )
        ).scalar_one()
        or 0
    )
    open_tracking_exceptions = int(
        (
            await session.execute(
                select(func.count(TrackingException.id)).where(
                    TrackingException.status != "RESOLVED"
                )
            )
        ).scalar_one()
        or 0
    )
    critical_exceptions = int(
        (
            await session.execute(
                select(func.count(TrackingException.id)).where(
                    TrackingException.status != "RESOLVED",
                    TrackingException.severity == "CRITICAL",
                )
            )
        ).scalar_one()
        or 0
    )
    active_disruptions = int(
        (
            await session.execute(
                select(func.count(DisruptionAlert.id)).where(DisruptionAlert.active.is_(True))
            )
        ).scalar_one()
        or 0
    )
    pending_route_recommendations = int(
        (
            await session.execute(
                select(func.count(RouteRecommendation.id)).where(
                    RouteRecommendation.status == "PENDING_REVIEW"
                )
            )
        ).scalar_one()
        or 0
    )
    pending_comm_approvals = int(
        (
            await session.execute(
                select(func.count(CarrierCommunication.id)).where(
                    CarrierCommunication.status.in_(["DRAFT", "PENDING_APPROVAL"])
                )
            )
        ).scalar_one()
        or 0
    )
    sent_comms = int(
        (
            await session.execute(
                select(func.count(CarrierCommunication.id)).where(
                    CarrierCommunication.status == "SENT"
                )
            )
        ).scalar_one()
        or 0
    )
    open_inventory_alerts = int(
        (
            await session.execute(
                select(func.count(InventoryAlert.id)).where(InventoryAlert.status != "RESOLVED")
            )
        ).scalar_one()
        or 0
    )
    exposure_raw = (
        await session.execute(
            select(func.coalesce(func.sum(InventoryAlert.financial_impact_usd), 0.0)).where(
                InventoryAlert.status != "RESOLVED"
            )
        )
    ).scalar_one()
    inventory_exposure_usd = round(float(exposure_raw or 0.0), 2)

    total_audit_entries = int(
        (await session.execute(select(func.count(AuditLog.id)))).scalar_one() or 0
    )
    recent_rows = (
        await session.execute(select(AuditLog).order_by(AuditLog.sequence_number.desc()).limit(10))
    ).scalars().all()

    return DashboardSummaryResponse(
        total_shipments=total_shipments,
        delayed_shipments=delayed_shipments,
        open_tracking_exceptions=open_tracking_exceptions,
        critical_exceptions=critical_exceptions,
        active_disruptions=active_disruptions,
        pending_route_recommendations=pending_route_recommendations,
        pending_comm_approvals=pending_comm_approvals,
        sent_comms=sent_comms,
        open_inventory_alerts=open_inventory_alerts,
        inventory_exposure_usd=inventory_exposure_usd,
        total_audit_entries=total_audit_entries,
        recent_audit_logs=[AuditLogRead.from_orm_model(entry) for entry in recent_rows],
    )
