import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings, validate_production_security
from app.core.logging import configure_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.seed import seed_demo_workspace
from app.core.telemetry import configure_telemetry
from app.db.session import create_engine_and_sessionmaker, ensure_db_initialized
from app.llm.router import LLMRouter


def create_app(settings_override: Settings | None = None) -> FastAPI:
    """Construct and configure the FastAPI application."""
    cfg = settings_override or get_settings()
    configure_logging(cfg.log_level)
    validate_production_security(cfg)

    engine, session_factory = create_engine_and_sessionmaker(cfg.database_url)
    llm_router = LLMRouter(cfg)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await ensure_db_initialized(application)
        if cfg.seed_demo_data:
            async with application.state.session_factory() as session:
                await seed_demo_workspace(session, application.state.llm_router)
        try:
            yield
        finally:
            await application.state.engine.dispose()

    application = FastAPI(
        title=cfg.app_name,
        version="0.1.0",
        description=(
            "Open-source, self-hosted AI logistics coordination platform for freight "
            "tracking, shipment route optimization, carrier communications, and inventory "
            "discrepancy alerts."
        ),
        lifespan=lifespan,
    )
    application.state.settings = cfg
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.db_init_lock = asyncio.Lock()
    application.state.db_initialized = False
    application.state.llm_router = llm_router

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RateLimitMiddleware, settings=cfg)
    application.add_middleware(SecurityHeadersMiddleware, settings=cfg)
    application.include_router(api_v1_router, prefix=cfg.api_v1_prefix)
    configure_telemetry(application, cfg)
    return application


app = create_app()
