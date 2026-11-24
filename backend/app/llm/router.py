from fastapi import Request

from app.core.config import Settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider, LLMRequest, LLMResponse
from app.llm.providers import GeminiLLMProvider, MockLLMProvider, OllamaLLMProvider

logger = get_logger(__name__)


class LLMRouter:
    """Ordered local-first LLM router with deterministic fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.providers: dict[str, LLMProvider] = {
            "mock": MockLLMProvider(),
            "ollama": OllamaLLMProvider(settings),
            "gemini": GeminiLLMProvider(settings),
        }

        ordered: list[str] = []
        for candidate in [settings.llm_default_provider.lower(), *settings.llm_fallback_list]:
            if candidate in self.providers and candidate not in ordered:
                ordered.append(candidate)
        if "mock" not in ordered:
            ordered.append("mock")
        self.provider_chain = ordered

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute LLM request across configured provider chain with automatic fallback."""
        errors: list[str] = []
        for index, provider_name in enumerate(self.provider_chain):
            provider = self.providers[provider_name]
            try:
                response = await provider.generate(request)
                response.fallback_used = index > 0
                return response
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                logger.warning(
                    "llm_provider_failed",
                    provider=provider_name,
                    task_type=request.task_type,
                    error=str(exc),
                )

        raise RuntimeError("All LLM providers failed: " + " | ".join(errors))


def get_llm_router(request: Request) -> LLMRouter:
    """FastAPI dependency returning the app-scoped LLMRouter."""
    router: LLMRouter = request.app.state.llm_router
    return router
