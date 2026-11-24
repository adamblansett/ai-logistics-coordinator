import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_tracking_webhook_edi214_and_exception_lifecycle(client: AsyncClient) -> None:
    sla = (datetime.now(UTC) + timedelta(hours=10)).isoformat()
    create_res = await client.post(
        "/api/v1/tracking/shipments",
        json={
            "reference_number": "SHP-TEST-101",
            "bol_number": "BOL-EDI-101",
            "pro_number": "PRO-EDI-101",
            "carrier_scac": "CRST",
            "carrier_name": "CrestLine Logistics",
            "mode": "FTL",
            "origin": "Los Angeles, CA",
            "destination": "Chicago, IL",
            "sla_eta": sla,
            "weight_lbs": 32000,
            "temperature_controlled": True,
        },
    )
    assert create_res.status_code == 201
    shipment = create_res.json()
    shipment_id = shipment["id"]
    assert shipment["status"] == "PLANNED"

    # 1. Ingest JSON webhook delay event -> opens exception
    delayed_eta = (datetime.now(UTC) + timedelta(hours=15)).isoformat()
    webhook_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "event_code": "DELAYED",
            "location": "Flagstaff, AZ",
            "reported_eta": delayed_eta,
            "notes": "Chain restriction on I-40",
        },
    )
    assert webhook_res.status_code == 200
    body = webhook_res.json()
    assert body["shipment"]["status"] == "DELAYED"
    assert body["shipment"]["delay_minutes"] >= 240
    assert body["exception"] is not None
    assert body["exception"]["exception_type"] == "ETA_SLIP"
    assert body["exception"]["severity"] == "CRITICAL"  # reefer >= 180m delay

    # 2. Second ETA_SLIP event updates existing exception without duplicating
    later_eta = (datetime.now(UTC) + timedelta(hours=16)).isoformat()
    second_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={
            "event_code": "DELAYED",
            "location": "Albuquerque, NM",
            "reported_eta": later_eta,
        },
    )
    assert second_res.status_code == 200
    exc_list_res = await client.get("/api/v1/tracking/exceptions")
    assert exc_list_res.status_code == 200
    eta_slip_exceptions = [
        item for item in exc_list_res.json() if item["exception_type"] == "ETA_SLIP"
    ]
    assert len(eta_slip_exceptions) == 1

    # 3. Ingest raw X12 EDI 214 auto-matched by BOL_NUMBER
    edi_eta_date = (datetime.now(UTC) + timedelta(days=2)).strftime("%Y%m%d")
    raw_edi = (
        f"B10*PRO-EDI-101*BOL-EDI-101*CRST~"
        f"AT7**NS*SD*BG*20261124*1430~"
        f"MS1*MEMPHIS*TN*US~"
        f"G62*17*{edi_eta_date}~"
    )
    edi_res = await client.post(
        "/api/v1/tracking/edi214",
        json={"raw_edi_214": raw_edi},
    )
    assert edi_res.status_code == 200
    edi_data = edi_res.json()
    assert edi_data["event"]["source_format"] == "EDI_214"
    assert edi_data["event"]["reason_code"] == "WEATHER"
    assert edi_data["shipment"]["last_location"] == "Memphis, TN"
    assert edi_data["exception"]["exception_type"] == "WEATHER_DISRUPTION"

    # 4. Acknowledge and resolve exception
    weather_exc_id = edi_data["exception"]["id"]
    ack_res = await client.patch(
        f"/api/v1/tracking/exceptions/{weather_exc_id}",
        json={"status": "ACKNOWLEDGED", "resolution_notes": "Monitoring storm corridor"},
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    res_res = await client.patch(
        f"/api/v1/tracking/exceptions/{weather_exc_id}",
        json={"status": "RESOLVED", "resolution_notes": "Cleared weather zone"},
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"
    assert res_res.json()["resolved_at"] is not None

    # 5. Deliver shipment and check detail view
    deliver_res = await client.post(
        f"/api/v1/tracking/shipments/{shipment_id}/events",
        json={"event_code": "DELIVERED", "location": "Chicago Dock 4"},
    )
    assert deliver_res.status_code == 200
    assert deliver_res.json()["shipment"]["status"] == "DELIVERED"

    detail_res = await client.get(f"/api/v1/tracking/shipments/{shipment_id}")
    assert detail_res.status_code == 200
    assert len(detail_res.json()["events"]) == 4


@pytest.mark.asyncio
async def test_webhook_hmac_signature_enforcement(tmp_path: Path) -> None:
    secret = "carrier-hmac-secret-123"
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'hmac.db').as_posix()}",
            webhook_signing_secret=secret,
        )
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ship_res = await ac.post(
                "/api/v1/tracking/shipments",
                json={
                    "reference_number": "SHP-HMAC-1",
                    "bol_number": "BOL-HMAC-1",
                    "pro_number": "PRO-HMAC-1",
                    "carrier_scac": "JBHT",
                    "carrier_name": "J.B. Hunt",
                    "origin": "Dallas, TX",
                    "destination": "Newark, NJ",
                    "sla_eta": (datetime.now(UTC) + timedelta(hours=12)).isoformat(),
                },
            )
            ship_id = ship_res.json()["id"]

            payload_bytes = json.dumps(
                {"event_code": "IN_TRANSIT", "location": "Memphis, TN"}
            ).encode("utf-8")

            bad_res = await ac.post(
                f"/api/v1/tracking/shipments/{ship_id}/events",
                content=payload_bytes,
                headers={"Content-Type": "application/json", "X-Webhook-Signature": "sha256=dead"},
            )
            assert bad_res.status_code == 401

            digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            good_res = await ac.post(
                f"/api/v1/tracking/shipments/{ship_id}/events",
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": f"sha256={digest}",
                },
            )
            assert good_res.status_code == 200
            assert good_res.json()["shipment"]["status"] == "IN_TRANSIT"
    finally:
        await app.state.engine.dispose()
