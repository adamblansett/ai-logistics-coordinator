from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class CarrierLane(Base):
    """Contracted or spot carrier lane with cost, transit, SLA, and carbon attributes."""

    __tablename__ = "carrier_lanes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    carrier_scac: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    carrier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    origin_region: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    destination_region: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="FTL")
    base_rate_usd: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_surcharge_pct: Mapped[float] = mapped_column(Float, nullable=False, default=12.0)
    transit_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    carbon_kg_per_ton_mile: Mapped[float] = mapped_column(Float, nullable=False, default=0.16)
    supports_reefer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_weight_lbs: Mapped[float] = mapped_column(Float, nullable=False, default=45000.0)
    disruption_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class DisruptionAlert(Base):
    """Active weather, port, highway, or capacity disruption impacting corridor routing."""

    __tablename__ = "disruption_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    region: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disruption_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    added_transit_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_surcharge_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class RouteRecommendation(Base):
    """Scored carrier/lane re-routing recommendation subject to dispatcher review."""

    __tablename__ = "route_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shipment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    origin_region: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_region: Mapped[str] = mapped_column(String(128), nullable=False)
    objective: Mapped[str] = mapped_column(String(32), nullable=False)
    recommended_lane_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("carrier_lanes.id", ondelete="CASCADE"), nullable=False
    )
    recommended_carrier_scac: Mapped[str] = mapped_column(String(16), nullable=False)
    recommended_carrier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    recommended_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_transit_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_reliability: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_carbon_kg: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    alternatives_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING_REVIEW", index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
