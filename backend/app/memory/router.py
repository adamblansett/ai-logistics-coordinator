from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal, require_roles, resolve_actor
from app.core.config import Settings, get_runtime_settings
from app.db.session import get_db
from app.memory.schemas import MemoryCreateRequest, MemorySearchHit, OperationalMemoryRead
from app.memory.service import index_memory, list_memories, search_memories

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=list[OperationalMemoryRead])
async def list_memories_endpoint(
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_db),
) -> list[OperationalMemoryRead]:
    items = await list_memories(session, category=category, limit=limit)
    return [OperationalMemoryRead.from_orm_model(item) for item in items]


@router.post("", response_model=OperationalMemoryRead, status_code=status.HTTP_201_CREATED)
async def create_memory_endpoint(
    payload: MemoryCreateRequest,
    principal: Principal = Depends(require_roles("DISPATCHER", "WAREHOUSE")),
    settings: Settings = Depends(get_runtime_settings),
    session: AsyncSession = Depends(get_db),
) -> OperationalMemoryRead:
    memory = await index_memory(
        session,
        category=payload.category,
        title=payload.title,
        content=payload.content,
        entity_id=payload.entity_id,
        corridor=payload.corridor,
        carrier_scac=payload.carrier_scac,
        metadata=payload.metadata,
        actor=resolve_actor(principal, payload.actor),
        dimensions=settings.embedding_dimensions,
    )
    return OperationalMemoryRead.from_orm_model(memory)


@router.get("/search", response_model=list[MemorySearchHit])
async def search_memories_endpoint(
    q: str = Query(min_length=1),
    category: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=25),
    _: Principal = Depends(get_current_principal),
    settings: Settings = Depends(get_runtime_settings),
    session: AsyncSession = Depends(get_db),
) -> list[MemorySearchHit]:
    return await search_memories(
        session,
        q,
        category=category,
        limit=limit,
        dimensions=settings.embedding_dimensions,
    )
