from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_runtime_settings
from app.core.security import verify_webhook_signature
from app.db.session import get_db
from app.tracking.normalizer import normalize_webhook_event, parse_edi_214
from app.tracking.schemas import (
    EDI214IngestRequest,
    EventIngestResponse,
    ShipmentCreate,
    ShipmentDetailRead,
    ShipmentRead,
    TrackingEventRead,
    TrackingExceptionRead,
    TrackingExceptionUpdate,
    WebhookEventCreate,
)
from app.tracking.service import (
    create_shipment,
    find_shipment_by_edi_identifiers,
    get_shipment_detail,
    get_shipment_or_404,
    ingest_event,
    list_exceptions,
    list_shipments,
    update_exception_status,
)

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get("/shipments", response_model=list[ShipmentRead])
async def get_shipments(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[ShipmentRead]:
    shipments = await list_shipments(session, status_filter=status_filter, search=search)
    return [ShipmentRead.model_validate(item) for item in shipments]


@router.post("/shipments", response_model=ShipmentRead, status_code=status.HTTP_201_CREATED)
async def create_shipment_endpoint(
    payload: ShipmentCreate,
    session: AsyncSession = Depends(get_db),
) -> ShipmentRead:
    shipment = await create_shipment(session, payload)
    return ShipmentRead.model_validate(shipment)


@router.get("/shipments/{shipment_id}", response_model=ShipmentDetailRead)
async def get_shipment_detail_endpoint(
    shipment_id: str,
    session: AsyncSession = Depends(get_db),
) -> ShipmentDetailRead:
    return await get_shipment_detail(session, shipment_id)


@router.post("/shipments/{shipment_id}/events", response_model=EventIngestResponse)
async def ingest_shipment_event_endpoint(
    shipment_id: str,
    payload: WebhookEventCreate,
    request: Request,
    x_webhook_signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
    settings: Settings = Depends(get_runtime_settings),
    session: AsyncSession = Depends(get_db),
) -> EventIngestResponse:
    raw_body = await request.body()
    if not verify_webhook_signature(
        raw_body, x_webhook_signature, settings.webhook_signing_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Webhook-Signature header.",
        )

    shipment = await get_shipment_or_404(session, shipment_id)
    if payload.raw_edi_214:
        try:
            normalized = parse_edi_214(payload.raw_edi_214)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    else:
        normalized = normalize_webhook_event(payload)

    event, updated_shipment, exception = await ingest_event(
        session,
        shipment,
        normalized,
        raw_payload=payload.model_dump(mode="json"),
        actor=payload.actor,
    )
    return EventIngestResponse(
        event=TrackingEventRead.model_validate(event),
        shipment=ShipmentRead.model_validate(updated_shipment),
        exception=TrackingExceptionRead.model_validate(exception) if exception else None,
    )


@router.post("/edi214", response_model=EventIngestResponse)
async def ingest_edi214_endpoint(
    payload: EDI214IngestRequest,
    session: AsyncSession = Depends(get_db),
) -> EventIngestResponse:
    try:
        normalized = parse_edi_214(payload.raw_edi_214)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    shipment = await find_shipment_by_edi_identifiers(
        session,
        bol_number=normalized.bol_number,
        pro_number=normalized.pro_number,
        reference_number=normalized.reference_number,
    )
    event, updated_shipment, exception = await ingest_event(
        session,
        shipment,
        normalized,
        raw_payload={"raw_edi_214": payload.raw_edi_214},
        actor=payload.actor,
    )
    return EventIngestResponse(
        event=TrackingEventRead.model_validate(event),
        shipment=ShipmentRead.model_validate(updated_shipment),
        exception=TrackingExceptionRead.model_validate(exception) if exception else None,
    )


@router.get("/exceptions", response_model=list[TrackingExceptionRead])
async def get_exceptions_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[TrackingExceptionRead]:
    exceptions = await list_exceptions(
        session,
        status_filter=status_filter,
        severity_filter=severity,
    )
    return [TrackingExceptionRead.model_validate(item) for item in exceptions]


@router.patch("/exceptions/{exception_id}", response_model=TrackingExceptionRead)
async def update_exception_endpoint(
    exception_id: str,
    payload: TrackingExceptionUpdate,
    session: AsyncSession = Depends(get_db),
) -> TrackingExceptionRead:
    exc = await update_exception_status(
        session,
        exception_id,
        new_status=payload.status,
        actor=payload.actor,
        resolution_notes=payload.resolution_notes,
    )
    return TrackingExceptionRead.model_validate(exc)
