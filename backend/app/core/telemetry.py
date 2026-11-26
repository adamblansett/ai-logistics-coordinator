import importlib

from fastapi import FastAPI

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_telemetry(app: FastAPI, settings: Settings) -> bool:
    """Enable OpenTelemetry FastAPI instrumentation when OTEL_ENABLED=true and SDK is present."""
    if not settings.otel_enabled:
        return False

    try:
        instr_mod = importlib.import_module("opentelemetry.instrumentation.fastapi")
        instrumentor = getattr(instr_mod, "FastAPIInstrumentor", None)
        if instrumentor is None:
            logger.warning("otel_instrumentor_unavailable")
            return False
        instrumentor.instrument_app(app)
        logger.info("otel_enabled", service=settings.app_slug)
        return True
    except ImportError:
        logger.warning(
            "otel_sdk_not_installed",
            detail="Install opentelemetry-instrumentation-fastapi to emit OTLP spans.",
        )
        return False
