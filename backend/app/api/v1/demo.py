from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.seed import seed_demo_workspace
from app.db.session import get_db
from app.llm.router import LLMRouter, get_llm_router

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoSeedResponse(BaseModel):
    seeded: bool
    message: str
    counts: dict[str, Any]


@router.post("/seed", response_model=DemoSeedResponse)
async def seed_demo_endpoint(
    session: AsyncSession = Depends(get_db),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> DemoSeedResponse:
    """Idempotently populate realistic demo shipments, lanes, drafts, and inventory alerts."""
    result = await seed_demo_workspace(session, llm_router)
    return DemoSeedResponse(**result)
