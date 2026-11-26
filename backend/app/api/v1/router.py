from fastapi import APIRouter

from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.demo import router as demo_router
from app.api.v1.health import router as health_router
from app.api.v1.workers import router as workers_router
from app.comms.router import router as comms_router
from app.inventory.router import router as inventory_router
from app.memory.router import router as memory_router
from app.routing.router import router as routing_router
from app.tracking.router import router as tracking_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(demo_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(workers_router)
api_v1_router.include_router(tracking_router)
api_v1_router.include_router(routing_router)
api_v1_router.include_router(comms_router)
api_v1_router.include_router(inventory_router)
