from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.llm.router import LLMRouter, get_llm_router
from app.routing.schemas import (
    CarrierLaneCreate,
    CarrierLaneRead,
    DisruptionAlertCreate,
    DisruptionAlertRead,
    DisruptionAlertUpdate,
    RecommendationDecisionRequest,
    RouteOptimizeRequest,
    RouteRecommendationRead,
)
from app.routing.service import (
    create_disruption,
    create_lane,
    decide_recommendation,
    list_disruptions,
    list_lanes,
    list_recommendations,
    optimize_route,
    update_disruption,
)

router = APIRouter(prefix="/routing", tags=["routing"])


@router.get("/lanes", response_model=list[CarrierLaneRead])
async def get_lanes_endpoint(
    active_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
) -> list[CarrierLaneRead]:
    lanes = await list_lanes(session, active_only=active_only)
    return [CarrierLaneRead.model_validate(item) for item in lanes]


@router.post("/lanes", response_model=CarrierLaneRead, status_code=status.HTTP_201_CREATED)
async def create_lane_endpoint(
    payload: CarrierLaneCreate,
    session: AsyncSession = Depends(get_db),
) -> CarrierLaneRead:
    lane = await create_lane(session, payload)
    return CarrierLaneRead.model_validate(lane)


@router.get("/disruptions", response_model=list[DisruptionAlertRead])
async def get_disruptions_endpoint(
    active_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
) -> list[DisruptionAlertRead]:
    alerts = await list_disruptions(session, active_only=active_only)
    return [DisruptionAlertRead.model_validate(item) for item in alerts]


@router.post(
    "/disruptions",
    response_model=DisruptionAlertRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_disruption_endpoint(
    payload: DisruptionAlertCreate,
    session: AsyncSession = Depends(get_db),
) -> DisruptionAlertRead:
    alert = await create_disruption(session, payload)
    return DisruptionAlertRead.model_validate(alert)


@router.patch("/disruptions/{disruption_id}", response_model=DisruptionAlertRead)
async def update_disruption_endpoint(
    disruption_id: str,
    payload: DisruptionAlertUpdate,
    session: AsyncSession = Depends(get_db),
) -> DisruptionAlertRead:
    alert = await update_disruption(session, disruption_id, payload)
    return DisruptionAlertRead.model_validate(alert)


@router.post(
    "/optimize",
    response_model=RouteRecommendationRead,
    status_code=status.HTTP_201_CREATED,
)
async def optimize_route_endpoint(
    payload: RouteOptimizeRequest,
    session: AsyncSession = Depends(get_db),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> RouteRecommendationRead:
    rec = await optimize_route(session, llm_router, payload)
    return RouteRecommendationRead.from_orm_model(rec)


@router.get("/recommendations", response_model=list[RouteRecommendationRead])
async def get_recommendations_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db),
) -> list[RouteRecommendationRead]:
    recs = await list_recommendations(session, status_filter=status_filter)
    return [RouteRecommendationRead.from_orm_model(item) for item in recs]


@router.post("/recommendations/{rec_id}/decision", response_model=RouteRecommendationRead)
async def decide_recommendation_endpoint(
    rec_id: str,
    payload: RecommendationDecisionRequest,
    session: AsyncSession = Depends(get_db),
) -> RouteRecommendationRead:
    rec = await decide_recommendation(
        session,
        rec_id,
        decision=payload.decision,
        actor=payload.actor,
        notes=payload.notes,
    )
    return RouteRecommendationRead.from_orm_model(rec)
