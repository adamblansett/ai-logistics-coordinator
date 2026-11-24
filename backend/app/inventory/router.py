from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.inventory.schemas import (
    InventoryAlertRead,
    InventoryAlertUpdate,
    InventoryReconciliationDetailRead,
    InventoryReconciliationRead,
    ReconciliationCreate,
)
from app.inventory.service import (
    get_reconciliation_detail,
    list_alerts,
    list_reconciliations,
    run_reconciliation,
    update_alert,
)
from app.llm.router import LLMRouter, get_llm_router

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/reconciliations", response_model=list[InventoryReconciliationRead])
async def get_reconciliations_endpoint(
    session: AsyncSession = Depends(get_db),
) -> list[InventoryReconciliationRead]:
    items = await list_reconciliations(session)
    return [InventoryReconciliationRead.from_orm_model(item) for item in items]


@router.post(
    "/reconcile",
    response_model=InventoryReconciliationRead,
    status_code=status.HTTP_201_CREATED,
)
async def reconcile_inventory_endpoint(
    payload: ReconciliationCreate,
    session: AsyncSession = Depends(get_db),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> InventoryReconciliationRead:
    rec = await run_reconciliation(session, llm_router, payload)
    return InventoryReconciliationRead.from_orm_model(rec)


@router.get("/reconciliations/{rec_id}", response_model=InventoryReconciliationDetailRead)
async def get_reconciliation_detail_endpoint(
    rec_id: str,
    session: AsyncSession = Depends(get_db),
) -> InventoryReconciliationDetailRead:
    return await get_reconciliation_detail(session, rec_id)


@router.get("/alerts", response_model=list[InventoryAlertRead])
async def get_inventory_alerts_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[InventoryAlertRead]:
    alerts = await list_alerts(
        session,
        status_filter=status_filter,
        severity_filter=severity,
    )
    return [InventoryAlertRead.model_validate(item) for item in alerts]


@router.patch("/alerts/{alert_id}", response_model=InventoryAlertRead)
async def update_inventory_alert_endpoint(
    alert_id: str,
    payload: InventoryAlertUpdate,
    session: AsyncSession = Depends(get_db),
) -> InventoryAlertRead:
    alert = await update_alert(
        session,
        alert_id,
        new_status=payload.status,
        actor=payload.actor,
        resolution_notes=payload.resolution_notes,
    )
    return InventoryAlertRead.model_validate(alert)
