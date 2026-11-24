from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.comms.schemas import (
    CarrierCommunicationRead,
    CommDecisionRequest,
    CommDraftRequest,
    CommSendRequest,
    CommUpdateRequest,
)
from app.comms.service import (
    decide_communication,
    draft_communication,
    get_communication_or_404,
    list_communications,
    send_communication,
    update_draft,
)
from app.db.session import get_db
from app.llm.router import LLMRouter, get_llm_router

router = APIRouter(prefix="/comms", tags=["comms"])


@router.get("", response_model=list[CarrierCommunicationRead])
async def get_communications_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    shipment_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[CarrierCommunicationRead]:
    items = await list_communications(
        session,
        status_filter=status_filter,
        shipment_id=shipment_id,
    )
    return [CarrierCommunicationRead.from_orm_model(item) for item in items]


@router.post(
    "/draft",
    response_model=CarrierCommunicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def draft_communication_endpoint(
    payload: CommDraftRequest,
    session: AsyncSession = Depends(get_db),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> CarrierCommunicationRead:
    comm = await draft_communication(session, llm_router, payload)
    return CarrierCommunicationRead.from_orm_model(comm)


@router.get("/{comm_id}", response_model=CarrierCommunicationRead)
async def get_communication_endpoint(
    comm_id: str,
    session: AsyncSession = Depends(get_db),
) -> CarrierCommunicationRead:
    comm = await get_communication_or_404(session, comm_id)
    return CarrierCommunicationRead.from_orm_model(comm)


@router.patch("/{comm_id}", response_model=CarrierCommunicationRead)
async def update_communication_endpoint(
    comm_id: str,
    payload: CommUpdateRequest,
    session: AsyncSession = Depends(get_db),
) -> CarrierCommunicationRead:
    comm = await update_draft(
        session,
        comm_id,
        subject=payload.subject,
        body=payload.body,
        actor=payload.actor,
    )
    return CarrierCommunicationRead.from_orm_model(comm)


@router.post("/{comm_id}/decision", response_model=CarrierCommunicationRead)
async def decide_communication_endpoint(
    comm_id: str,
    payload: CommDecisionRequest,
    session: AsyncSession = Depends(get_db),
) -> CarrierCommunicationRead:
    comm = await decide_communication(
        session,
        comm_id,
        decision=payload.decision,
        actor=payload.actor,
        notes=payload.notes,
    )
    return CarrierCommunicationRead.from_orm_model(comm)


@router.post("/{comm_id}/send", response_model=CarrierCommunicationRead)
async def send_communication_endpoint(
    comm_id: str,
    payload: CommSendRequest | None = Body(default=None),
    session: AsyncSession = Depends(get_db),
) -> CarrierCommunicationRead:
    actor = payload.actor if payload is not None else "dispatcher"
    comm = await send_communication(session, comm_id, actor=actor)
    return CarrierCommunicationRead.from_orm_model(comm)
