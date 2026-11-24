import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExpectedLineItem(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    description: str = Field(default="Freight SKU", max_length=255)
    expected_qty: int = Field(ge=0)
    unit_cost_usd: float = Field(default=0.0, ge=0.0)


class ReceivedLineItem(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=255)
    received_qty: int = Field(ge=0)
    damaged_qty: int = Field(default=0, ge=0)
    unit_cost_usd: float | None = Field(default=None, ge=0.0)


class ReconciliationCreate(BaseModel):
    shipment_id: str | None = None
    asn_number: str = Field(min_length=2, max_length=64)
    bol_number: str = Field(min_length=2, max_length=64)
    warehouse_code: str = Field(min_length=2, max_length=32)
    expected_lines: list[ExpectedLineItem] = Field(min_length=1)
    received_lines: list[ReceivedLineItem] = Field(default_factory=list)
    actor: str = Field(default="warehouse-receiver", max_length=128)


class DiscrepancyItemRead(BaseModel):
    sku: str
    description: str
    alert_type: str
    severity: str
    expected_qty: int
    received_qty: int
    damaged_qty: int
    variance_qty: int
    financial_impact_usd: float


class InventoryAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reconciliation_id: str
    shipment_id: str | None
    sku: str
    description: str
    alert_type: str
    severity: str
    expected_qty: int
    received_qty: int
    damaged_qty: int
    variance_qty: int
    financial_impact_usd: float
    status: str
    resolution_notes: str | None
    created_at: datetime
    resolved_at: datetime | None


class InventoryAlertUpdate(BaseModel):
    status: Literal["INVESTIGATING", "CLAIM_FILED", "RESOLVED"]
    resolution_notes: str | None = None
    actor: str = Field(default="inventory-analyst", max_length=128)


class InventoryReconciliationRead(BaseModel):
    id: str
    shipment_id: str | None
    asn_number: str
    bol_number: str
    warehouse_code: str
    expected_total_units: int
    received_total_units: int
    damaged_total_units: int
    variance_units: int
    shrinkage_pct: float
    financial_impact_usd: float
    status: str
    discrepancies: list[DiscrepancyItemRead]
    ai_summary: str
    llm_provider: str
    reconciled_by: str
    created_at: datetime

    @classmethod
    def from_orm_model(cls, model: Any) -> "InventoryReconciliationRead":
        raw_items = json.loads(model.discrepancies_json or "[]")
        return cls(
            id=model.id,
            shipment_id=model.shipment_id,
            asn_number=model.asn_number,
            bol_number=model.bol_number,
            warehouse_code=model.warehouse_code,
            expected_total_units=model.expected_total_units,
            received_total_units=model.received_total_units,
            damaged_total_units=model.damaged_total_units,
            variance_units=model.variance_units,
            shrinkage_pct=model.shrinkage_pct,
            financial_impact_usd=model.financial_impact_usd,
            status=model.status,
            discrepancies=[DiscrepancyItemRead.model_validate(item) for item in raw_items],
            ai_summary=model.ai_summary,
            llm_provider=model.llm_provider,
            reconciled_by=model.reconciled_by,
            created_at=model.created_at,
        )


class InventoryReconciliationDetailRead(InventoryReconciliationRead):
    alerts: list[InventoryAlertRead] = Field(default_factory=list)
