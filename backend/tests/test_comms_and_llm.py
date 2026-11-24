from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.security import redact_pii
from app.llm.base import LLMRequest
from app.llm.providers import GeminiLLMProvider
from app.llm.router import LLMRouter


def test_pii_redactor_scrubs_sensitive_categories() -> None:
    raw = (
        "Contact driver john.doe@carrier-example.com at 312-555-0199, "
        "SSN 123-45-6789, key sk-testsecret987654321."
    )
    redacted, categories = redact_pii(raw)
    assert "john.doe@carrier-example.com" not in redacted
    assert "312-555-0199" not in redacted
    assert "123-45-6789" not in redacted
    assert "sk-testsecret987654321" not in redacted
    assert categories == ["API_KEY", "EMAIL", "PHONE", "SSN"]


@pytest.mark.asyncio
async def test_llm_router_fallback_and_gemini_cloud_pii_scrubbing() -> None:
    router = LLMRouter(
        Settings(
            llm_default_provider="gemini",
            llm_fallback_providers="mock",
            gemini_api_key="",
        )
    )
    res = await router.generate(
        LLMRequest(
            task_type="exception_summary",
            system_prompt="Summarize exception.",
            user_prompt="Summarize SHP-1.",
            context={
                "reference_number": "SHP-1",
                "exception_type": "ETA_SLIP",
                "delay_minutes": 90,
            },
        )
    )
    assert res.provider == "mock"
    assert res.fallback_used is True
    assert "SHP-1" in res.content

    captured_payload: dict[str, Any] = {}

    class _FakeResponse:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "SUBJECT: Clean Update\n\nBody OK."}]}}
                ]
            }

    async def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        captured_payload["json"] = kwargs.get("json")
        return _FakeResponse()

    provider = GeminiLLMProvider(
        Settings(
            gemini_api_key="AIzaDummyKeyForUnitTestOnly123",
            llm_redact_pii_for_cloud=True,
        )
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_post)):
        cloud_res = await provider.generate(
            LLMRequest(
                task_type="carrier_comm",
                system_prompt="Email dispatch@carrier.io",
                user_prompt="Driver phone 415-555-0144 SSN 999-88-7777",
            )
        )

    assert cloud_res.pii_redacted is True
    assert cloud_res.redacted_categories == ["EMAIL", "PHONE", "SSN"]
    sent_text = json_dumps_safe(captured_payload["json"])
    assert "dispatch@carrier.io" not in sent_text
    assert "415-555-0144" not in sent_text
    assert "999-88-7777" not in sent_text


def json_dumps_safe(obj: Any) -> str:
    import json

    return json.dumps(obj)


@pytest.mark.asyncio
async def test_carrier_comm_human_in_the_loop_send_gating(client: AsyncClient) -> None:
    ship_res = await client.post(
        "/api/v1/tracking/shipments",
        json={
            "reference_number": "SHP-COMM-55",
            "bol_number": "BOL-COMM-55",
            "pro_number": "PRO-COMM-55",
            "carrier_scac": "ODFL",
            "carrier_name": "Old Dominion Freight",
            "origin": "Seattle, WA",
            "destination": "Denver, CO",
            "sla_eta": (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
        },
    )
    ship_id = ship_res.json()["id"]

    draft_res = await client.post(
        "/api/v1/comms/draft",
        json={
            "shipment_id": ship_id,
            "comm_type": "DETENTION_NOTICE",
            "channel": "EMAIL",
            "recipient_name": "ODFL Dock Desk",
            "recipient_contact": "dock@odfl-example.com",
            "custom_notes": "Gate arrival verified 06:15 MST.",
        },
    )
    assert draft_res.status_code == 201
    comm = draft_res.json()
    comm_id = comm["id"]
    assert comm["status"] == "PENDING_APPROVAL"
    assert "BOL-COMM-55" in comm["body"]
    assert "SHP-COMM-55" in comm["subject"]

    # Must block sending prior to dispatcher approval
    blocked_send = await client.post(f"/api/v1/comms/{comm_id}/send")
    assert blocked_send.status_code == 409

    # Dispatcher edits draft before approval
    edit_res = await client.patch(
        f"/api/v1/comms/{comm_id}",
        json={"subject": "Approved Detention Notice — SHP-COMM-55 (BOL-COMM-55)"},
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["subject"].startswith("Approved Detention Notice")

    # Approve draft
    approve_res = await client.post(
        f"/api/v1/comms/{comm_id}/decision",
        json={"decision": "APPROVED", "actor": "lead-dispatcher", "notes": "Verified gate log"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # Send approved message -> SENT with external_message_id
    send_res = await client.post(f"/api/v1/comms/{comm_id}/send")
    assert send_res.status_code == 200
    sent_data = send_res.json()
    assert sent_data["status"] == "SENT"
    assert sent_data["external_message_id"].startswith("MSG-")

    # Cannot re-send already sent communication
    resend_res = await client.post(f"/api/v1/comms/{comm_id}/send")
    assert resend_res.status_code == 409
