from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class Shipment(Base):
    """Tracked freight shipment with SLA ETA and delay telemetry."""

    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    reference_number: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    bol_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pro_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    carrier_scac: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    carrier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="FTL")
    origin: Mapped[str] = mapped_column(String(128), nullable=False)
    destination: Mapped[str] = mapped_column(String(128), nullable=False)
    last_location: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED", index=True)
    sla_eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight_lbs: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)
    temperature_controlled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class TrackingEvent(Base):
    """Normalized carrier milestone ingested from webhook JSON, EDI 214, or manual updates."""

    __tablename__ = "tracking_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shipment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_format: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_code: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class TrackingException(Base):
    """SLA slip or operational exception surfaced by the tracking detector."""

    __tablename__ = "tracking_exceptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shipment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exception_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
