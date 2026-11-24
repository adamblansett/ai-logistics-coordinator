from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class CarrierCommunication(Base):
    """Grounded carrier communication draft gated behind human-in-the-loop approval."""

    __tablename__ = "carrier_communications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shipment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    comm_type: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="EMAIL")
    recipient_name: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_contact: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    grounding_facts_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(64), nullable=False)
    pii_redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redacted_categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING_APPROVAL", index=True
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="dispatcher")
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
