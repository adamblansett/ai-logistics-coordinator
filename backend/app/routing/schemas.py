import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RoutingObjective = Literal[
    "BALANCED",
    "LOWEST_COST",
    "FASTEST_TRANSIT",
    "HIGHEST_RELIABILITY",
    "LOWEST_CARBON",
]
DisruptionType = Literal[
    "WEATHER",
    "PORT_CONGESTION",
    "HIGHWAY_CLOSURE",
    "LABOR_ACTION",
    "CARRIER_CAPACITY",
]
SeverityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
LaneMode = Literal["FTL", "LTL", "INTERMODAL", "OCEAN", "AIR"]


class CarrierLaneCreate(BaseModel):
    carrier_scac: str = Field(min_length=2, max_length=16)
    carrier_name: str = Field(min_length=2, max_length=128)
    origin_region: str = Field(min_length=2, max_length=128)
    destination_region: str = Field(min_length=2, max_length=128)
    mode: LaneMode = "FTL"
    base_rate_usd: float = Field(gt=0)
    fuel_surcharge_pct: float = Field(default=12.0, ge=0, le=100)
    transit_hours: int = Field(gt=0)
    on_time_rate: float = Field(default=0.95, ge=0.1, le=1.0)
    carbon_kg_per_ton_mile: float = Field(default=0.16, gt=0)
    supports_reefer: bool = False
    max_weight_lbs: float = Field(default=45000.0, gt=0)
    disruption_risk_score: float = Field(default=0.1, ge=0.0, le=1.0)
    active: bool = True
    actor: str = Field(default="dispatcher", max_length=128)


class CarrierLaneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    carrier_scac: str
    carrier_name: str
    origin_region: str
    destination_region: str
    mode: str
    base_rate_usd: float
    fuel_surcharge_pct: float
    transit_hours: int
    on_time_rate: float
    carbon_kg_per_ton_mile: float
    supports_reefer: bool
    max_weight_lbs: float
    disruption_risk_score: float
    active: bool
    created_at: datetime


class DisruptionAlertCreate(BaseModel):
    region: str = Field(min_length=2, max_length=128)
    disruption_type: DisruptionType
    severity: SeverityLevel
    added_transit_hours: int = Field(default=0, ge=0)
    cost_surcharge_pct: float = Field(default=0.0, ge=0, le=200)
    description: str = Field(min_length=3)
    active: bool = True
    actor: str = Field(default="operations-monitor", max_length=128)


class DisruptionAlertUpdate(BaseModel):
    active: bool | None = None
    severity: SeverityLevel | None = None
    added_transit_hours: int | None = Field(default=None, ge=0)
    cost_surcharge_pct: float | None = Field(default=None, ge=0, le=200)
    description: str | None = None
    actor: str = Field(default="dispatcher", max_length=128)


class DisruptionAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    region: str
    disruption_type: str
    severity: str
    added_transit_hours: int
    cost_surcharge_pct: float
    description: str
    active: bool
    created_at: datetime


class RouteOptimizeRequest(BaseModel):
    shipment_id: str | None = None
    origin_region: str | None = None
    destination_region: str | None = None
    weight_lbs: float | None = Field(default=None, gt=0)
    temperature_controlled: bool | None = None
    objective: RoutingObjective = "BALANCED"
    max_budget_usd: float | None = Field(default=None, gt=0)
    max_transit_hours: int | None = Field(default=None, gt=0)
    actor: str = Field(default="dispatcher", max_length=128)


class RouteAlternativeRead(BaseModel):
    lane_id: str
    carrier_scac: str
    carrier_name: str
    mode: str
    estimated_cost_usd: float
    estimated_transit_hours: int
    estimated_reliability: float
    estimated_carbon_kg: float
    composite_score: float


class RouteRecommendationRead(BaseModel):
    id: str
    shipment_id: str | None
    origin_region: str
    destination_region: str
    objective: str
    recommended_lane_id: str
    recommended_carrier_scac: str
    recommended_carrier_name: str
    recommended_mode: str
    estimated_cost_usd: float
    estimated_transit_hours: int
    estimated_reliability: float
    estimated_carbon_kg: float
    composite_score: float
    alternatives: list[RouteAlternativeRead]
    rationale: str
    llm_provider: str
    status: str
    reviewed_by: str | None
    review_notes: str | None
    created_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_orm_model(cls, model: Any) -> "RouteRecommendationRead":
        raw_alts = json.loads(model.alternatives_json or "[]")
        return cls(
            id=model.id,
            shipment_id=model.shipment_id,
            origin_region=model.origin_region,
            destination_region=model.destination_region,
            objective=model.objective,
            recommended_lane_id=model.recommended_lane_id,
            recommended_carrier_scac=model.recommended_carrier_scac,
            recommended_carrier_name=model.recommended_carrier_name,
            recommended_mode=model.recommended_mode,
            estimated_cost_usd=model.estimated_cost_usd,
            estimated_transit_hours=model.estimated_transit_hours,
            estimated_reliability=model.estimated_reliability,
            estimated_carbon_kg=model.estimated_carbon_kg,
            composite_score=model.composite_score,
            alternatives=[RouteAlternativeRead.model_validate(item) for item in raw_alts],
            rationale=model.rationale,
            llm_provider=model.llm_provider,
            status=model.status,
            reviewed_by=model.reviewed_by,
            review_notes=model.review_notes,
            created_at=model.created_at,
            reviewed_at=model.reviewed_at,
        )


class RecommendationDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    actor: str = Field(default="dispatcher", min_length=1, max_length=128)
    notes: str | None = None
