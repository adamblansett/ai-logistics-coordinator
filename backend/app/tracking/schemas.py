from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ShipmentMode = Literal["FTL", "LTL", "INTERMODAL", "OCEAN", "AIR"]
ShipmentStatus = Literal[
    "PLANNED",
    "PICKED_UP",
    "IN_TRANSIT",
    "DELAYED",
    "EXCEPTION",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
]
ExceptionStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]


class ShipmentCreate(BaseModel):
    reference_number: str = Field(min_length=2, max_length=64)
    bol_number: str = Field(min_length=2, max_length=64)
    pro_number: str = Field(min_length=2, max_length=64)
    carrier_scac: str = Field(min_length=2, max_length=16)
    carrier_name: str = Field(min_length=2, max_length=128)
    mode: ShipmentMode = "FTL"
    origin: str = Field(min_length=2, max_length=128)
    destination: str = Field(min_length=2, max_length=128)
    last_location: str | None = Field(default=None, max_length=128)
    sla_eta: datetime
    current_eta: datetime | None = None
    weight_lbs: float = Field(default=10000.0, gt=0)
    temperature_controlled: bool = False
    actor: str = Field(default="dispatcher", max_length=128)


class ShipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference_number: str
    bol_number: str
    pro_number: str
    carrier_scac: str
    carrier_name: str
    mode: str
    origin: str
    destination: str
    last_location: str
    status: str
    sla_eta: datetime
    current_eta: datetime
    delay_minutes: int
    weight_lbs: float
    temperature_controlled: bool
    created_at: datetime
    updated_at: datetime


class TrackingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shipment_id: str
    source_format: str
    raw_code: str
    normalized_status: str
    reason_code: str | None
    location: str
    event_timestamp: datetime
    reported_eta: datetime | None
    notes: str
    raw_payload: str
    created_at: datetime


class TrackingExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shipment_id: str
    exception_type: str
    severity: str
    status: str
    delay_minutes: int
    summary: str
    resolution_notes: str | None
    detected_at: datetime
    resolved_at: datetime | None


class ShipmentDetailRead(ShipmentRead):
    events: list[TrackingEventRead] = Field(default_factory=list)
    exceptions: list[TrackingExceptionRead] = Field(default_factory=list)


class WebhookEventCreate(BaseModel):
    raw_edi_214: str | None = None
    event_code: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=64)
    reason_code: str | None = Field(default=None, max_length=64)
    location: str = Field(default="In Transit", max_length=128)
    event_timestamp: datetime | None = None
    reported_eta: datetime | None = None
    notes: str = ""
    actor: str = Field(default="carrier-webhook", max_length=128)

    @model_validator(mode="after")
    def validate_event_source(self) -> "WebhookEventCreate":
        if not self.raw_edi_214 and not self.event_code and not self.status:
            raise ValueError("Provide either raw_edi_214 or event_code/status.")
        return self


class EDI214IngestRequest(BaseModel):
    raw_edi_214: str = Field(min_length=5)
    actor: str = Field(default="edi-gateway", max_length=128)


class TrackingExceptionUpdate(BaseModel):
    status: Literal["ACKNOWLEDGED", "RESOLVED"]
    resolution_notes: str | None = None
    actor: str = Field(default="dispatcher", max_length=128)


class EventIngestResponse(BaseModel):
    event: TrackingEventRead
    shipment: ShipmentRead
    exception: TrackingExceptionRead | None = None
