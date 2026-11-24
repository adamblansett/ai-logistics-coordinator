from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """Structured prompt & domain context passed to an LLM provider."""

    task_type: Literal[
        "carrier_comm",
        "route_rationale",
        "exception_summary",
        "inventory_discrepancy",
    ]
    system_prompt: str
    user_prompt: str
    context: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Normalized LLM output with provider provenance and PII redaction metadata."""

    provider: str
    model: str
    content: str
    pii_redacted: bool = False
    redacted_categories: list[str] = Field(default_factory=list)
    fallback_used: bool = False


class LLMProvider(Protocol):
    """Common async contract implemented by mock, local Ollama, and cloud Gemini adapters."""

    name: str
    model: str

    async def generate(self, request: LLMRequest) -> LLMResponse: ...
