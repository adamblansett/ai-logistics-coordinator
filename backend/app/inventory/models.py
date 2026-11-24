from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class InventoryReconciliation(Base):
    """ASN/BOL vs. warehouse receiving count reconciliation run."""

    __tablename__ = "inventory_reconciliations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shipment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    asn_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bol_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    warehouse_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    expected_total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    received_total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    damaged_total_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    variance_units: Mapped[int] = mapped_column(Integer, nullable=False)
    shrinkage_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    financial_impact_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MATCHED", index=True
    )
    discrepancies_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    reconciled_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class InventoryAlert(Base):
    """SKU-level shortage, overage, damage, or unexpected receipt discrepancy alert."""

    __tablename__ = "inventory_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    reconciliation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inventory_reconciliations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shipment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    expected_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    damaged_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    variance_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    financial_impact_usd: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
