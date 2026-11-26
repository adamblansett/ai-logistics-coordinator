import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.db.base import new_uuid, utcnow
from app.memory.embeddings import cosine_similarity, embed_text
from app.memory.models import OperationalMemory
from app.memory.schemas import MemorySearchHit, OperationalMemoryRead


async def index_memory(
    session: AsyncSession,
    *,
    category: str,
    title: str,
    content: str,
    entity_id: str | None = None,
    corridor: str | None = None,
    carrier_scac: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor: str = "system",
    dimensions: int = 64,
    commit: bool = True,
) -> OperationalMemory:
    """Index an operational resolution or playbook entry with its normalized vector."""
    clean_title = title.strip()
    clean_content = content.strip()
    searchable = " ".join(
        part
        for part in (category, corridor or "", carrier_scac or "", clean_title, clean_content)
        if part
    )
    vector = embed_text(searchable, dimensions=dimensions)

    memory = OperationalMemory(
        id=new_uuid(),
        category=category.strip().upper(),
        entity_id=entity_id,
        corridor=corridor.strip() if corridor else None,
        carrier_scac=carrier_scac.strip().upper() if carrier_scac else None,
        title=clean_title,
        content=clean_content,
        embedding_json=json.dumps(vector),
        metadata_json=json.dumps(metadata or {}, default=str),
        created_at=utcnow(),
    )
    session.add(memory)
    await session.flush()

    await record_audit_event(
        session,
        entity_type="operational_memory",
        entity_id=memory.id,
        action="MEMORY_INDEXED",
        actor=actor,
        previous_state=None,
        new_state=memory.category,
        details={"title": memory.title, "corridor": memory.corridor},
    )
    if commit:
        await session.commit()
        await session.refresh(memory)
    return memory


async def list_memories(
    session: AsyncSession,
    *,
    category: str | None = None,
    limit: int = 50,
) -> list[OperationalMemory]:
    """List recent indexed operational memories."""
    stmt = select(OperationalMemory).order_by(OperationalMemory.created_at.desc()).limit(limit)
    if category:
        stmt = stmt.where(OperationalMemory.category == category.strip().upper())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_memories(
    session: AsyncSession,
    query: str,
    *,
    category: str | None = None,
    limit: int = 5,
    min_score: float = 0.05,
    dimensions: int = 64,
) -> list[MemorySearchHit]:
    """Retrieve top semantic matches across operational memories by cosine similarity."""
    clean_query = query.strip()
    if not clean_query:
        return []

    query_vec = embed_text(clean_query, dimensions=dimensions)
    stmt = select(OperationalMemory)
    if category:
        stmt = stmt.where(OperationalMemory.category == category.strip().upper())
    rows = list((await session.execute(stmt)).scalars().all())

    scored: list[MemorySearchHit] = []
    for row in rows:
        vec = [float(x) for x in json.loads(row.embedding_json or "[]")]
        if len(vec) != len(query_vec):
            searchable = " ".join(
                part
                for part in (
                    row.category,
                    row.corridor or "",
                    row.carrier_scac or "",
                    row.title,
                    row.content,
                )
                if part
            )
            vec = embed_text(searchable, dimensions=len(query_vec))
        score = cosine_similarity(query_vec, vec)
        if score >= min_score:
            scored.append(
                MemorySearchHit(
                    memory=OperationalMemoryRead.from_orm_model(row),
                    score=score,
                )
            )

    scored.sort(key=lambda hit: (-hit.score, hit.memory.created_at), reverse=False)
    return scored[:limit]
