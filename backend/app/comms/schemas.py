import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CommType = Literal[
    "DETENTION_NOTICE",
    "BOL_CORRECTION",
    "APPOINTMENT_RESCHEDULE",
    "DELAY_ESCALATION",
    "DISCREPANCY_CLAIM",
]
CommChannel = Literal["EMAIL", "EDI_PORTAL", "CARRIER_WEBHOOK"]


class CommDraftRequest(BaseModel):
    shipment_id: str
    comm_type: CommType = "DELAY_ESCALATION"
    channel: CommChannel = "EMAIL"
    recipient_name: str = Field(min_length=2, max_length=128)
    recipient_contact: str = Field(min_length=2, max_length=128)
    custom_notes: str = ""
    actor: str = Field(default="dispatcher", max_length=128)


class CommUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=255)
    body: str | None = Field(default=None, min_length=5)
    actor: str = Field(default="dispatcher", max_length=128)


class CommDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    actor: str = Field(default="dispatcher", min_length=1, max_length=128)
    notes: str | None = None


class CommSendRequest(BaseModel):
    actor: str = Field(default="dispatcher", min_length=1, max_length=128)


class CarrierCommunicationRead(BaseModel):
    id: str
    shipment_id: str
    comm_type: str
    channel: str
    recipient_name: str
    recipient_contact: str
    subject: str
    body: str
    grounding_facts: dict[str, Any]
    llm_provider: str
    llm_model: str
    pii_redacted: bool
    redacted_categories: list[str]
    status: str
    created_by: str
    reviewed_by: str | None
    review_notes: str | None
    external_message_id: str | None
    created_at: datetime
    reviewed_at: datetime | None
    sent_at: datetime | None

    @classmethod
    def from_orm_model(cls, model: Any) -> "CarrierCommunicationRead":
        return cls(
            id=model.id,
            shipment_id=model.shipment_id,
            comm_type=model.comm_type,
            channel=model.channel,
            recipient_name=model.recipient_name,
            recipient_contact=model.recipient_contact,
            subject=model.subject,
            body=model.body,
            grounding_facts=json.loads(model.grounding_facts_json or "{}"),
            llm_provider=model.llm_provider,
            llm_model=model.llm_model,
            pii_redacted=model.pii_redacted,
            redacted_categories=json.loads(model.redacted_categories_json or "[]"),
            status=model.status,
            created_by=model.created_by,
            reviewed_by=model.reviewed_by,
            review_notes=model.review_notes,
            external_message_id=model.external_message_id,
            created_at=model.created_at,
            reviewed_at=model.reviewed_at,
            sent_at=model.sent_at,
        )
