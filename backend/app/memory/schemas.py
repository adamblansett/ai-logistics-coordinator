import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

MemoryCategory = Literal[
    "TRACKING_EXCEPTION",
    "CARRIER_PERFORMANCE",
    "ROUTE_PLAYBOOK",
    "OSD_CLAIM",
    "GENERAL",
]


class MemoryCreateRequest(BaseModel):
    category: MemoryCategory = "GENERAL"
    entity_id: str | None = Field(default=None, max_length=64)
    corridor: str | None = Field(default=None, max_length=128)
    carrier_scac: str | None = Field(default=None, max_length=16)
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=5)
    metadata: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="dispatcher", max_length=128)


class OperationalMemoryRead(BaseModel):
    id: str
    category: str
    entity_id: str | None
    corridor: str | None
    carrier_scac: str | None
    title: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_orm_model(cls, model: Any) -> "OperationalMemoryRead":
        return cls(
            id=model.id,
            category=model.category,
            entity_id=model.entity_id,
            corridor=model.corridor,
            carrier_scac=model.carrier_scac,
            title=model.title,
            content=model.content,
            metadata=json.loads(model.metadata_json or "{}"),
            created_at=model.created_at,
        )


class MemorySearchHit(BaseModel):
    memory: OperationalMemoryRead
    score: float
