from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_auth_rbac_jwt_and_api_key_actor_attribution(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'rbac.db').as_posix()}",
            auth_enabled=True,
            rate_limit_enabled=False,
            auth_api_keys="edi-key-secret:WEBHOOK_INGESTOR:edi-gateway",
            auth_secret_key="test-secret-key-at-least-thirty-two-bytes-long",
        )
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Health probes remain open; protected API rejects unauthenticated callers
            assert (await ac.get("/api/v1/health/live")).status_code == 200
            assert (await ac.get("/api/v1/tracking/shipments")).status_code == 401

            # Bootstrap initial ADMIN account
            reg_admin = await ac.post(
                "/api/v1/auth/register",
                json={"username": "admin", "password": "AdminPassword123!", "role": "ADMIN"},
            )
            assert reg_admin.status_code == 201

            login_admin = await ac.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "AdminPassword123!"},
            )
            assert login_admin.status_code == 200
            admin_token = login_admin.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            # Non-admin cannot register accounts once bootstrapped
            reg_unauth = await ac.post(
                "/api/v1/auth/register",
                json={"username": "wh_user", "password": "WhPassword123!", "role": "WAREHOUSE"},
            )
            assert reg_unauth.status_code == 401

            # Admin registers WAREHOUSE user
            reg_wh = await ac.post(
                "/api/v1/auth/register",
                headers=admin_headers,
                json={"username": "wh_user", "password": "WhPassword123!", "role": "WAREHOUSE"},
            )
            assert reg_wh.status_code == 201

            wh_token = (
                await ac.post(
                    "/api/v1/auth/login",
                    json={"username": "wh_user", "password": "WhPassword123!"},
                )
            ).json()["access_token"]
            wh_headers = {"Authorization": f"Bearer {wh_token}"}

            me_res = await ac.get("/api/v1/auth/me", headers=wh_headers)
            assert me_res.status_code == 200
            assert me_res.json()["username"] == "wh_user"
            assert me_res.json()["role"] == "WAREHOUSE"

            # Warehouse user can reconcile inventory; verified identity overrides client actor
            recon_res = await ac.post(
                "/api/v1/inventory/reconcile",
                headers=wh_headers,
                json={
                    "asn_number": "ASN-RBAC-1",
                    "bol_number": "BOL-RBAC-1",
                    "warehouse_code": "ORD-1",
                    "expected_lines": [
                        {"sku": "SKU-1", "expected_qty": 10, "unit_cost_usd": 10.0}
                    ],
                    "received_lines": [{"sku": "SKU-1", "received_qty": 10, "damaged_qty": 0}],
                    "actor": "spoofed-client-actor",
                },
            )
            assert recon_res.status_code == 201
            assert recon_res.json()["reconciled_by"] == "wh_user"

            # Warehouse user cannot run route optimization or draft carrier comms
            assert (
                await ac.post(
                    "/api/v1/routing/optimize",
                    headers=wh_headers,
                    json={
                        "origin_region": "Chicago, IL",
                        "destination_region": "Dallas, TX",
                    },
                )
            ).status_code == 403
            assert (
                await ac.post(
                    "/api/v1/comms/draft",
                    headers=wh_headers,
                    json={
                        "shipment_id": "missing",
                        "recipient_name": "Desk",
                        "recipient_contact": "desk@example.com",
                    },
                )
            ).status_code == 403

            # Admin creates a shipment; X-API-Key WEBHOOK_INGESTOR ingests EDI 214
            ship_res = await ac.post(
                "/api/v1/tracking/shipments",
                headers=admin_headers,
                json={
                    "reference_number": "SHP-APIKEY-1",
                    "bol_number": "BOL-APIKEY-1",
                    "pro_number": "PRO-APIKEY-1",
                    "carrier_scac": "CRST",
                    "carrier_name": "CrestLine",
                    "origin": "Los Angeles, CA",
                    "destination": "Chicago, IL",
                    "sla_eta": (datetime.now(UTC) + timedelta(hours=12)).isoformat(),
                },
            )
            assert ship_res.status_code == 201

            api_key_headers = {"X-API-Key": "edi-key-secret"}
            edi_res = await ac.post(
                "/api/v1/tracking/edi214",
                headers=api_key_headers,
                json={
                    "raw_edi_214": (
                        "B10*PRO-APIKEY-1*BOL-APIKEY-1*CRST~"
                        "AT7*AF*NS***20261126*0800~MS1*DENVER*CO*US~"
                    ),
                    "actor": "spoofed-edi-sender",
                },
            )
            assert edi_res.status_code == 200

            audit_res = await ac.get("/api/v1/audit?action=EVENT_INGESTED", headers=admin_headers)
            assert audit_res.status_code == 200
            assert audit_res.json()[0]["actor"] == "edi-gateway"

            # API key WEBHOOK_INGESTOR cannot draft carrier comms
            assert (
                await ac.post(
                    "/api/v1/comms/draft",
                    headers=api_key_headers,
                    json={
                        "shipment_id": ship_res.json()["id"],
                        "recipient_name": "Desk",
                        "recipient_contact": "desk@example.com",
                    },
                )
            ).status_code == 403
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_rate_limiting_enforces_429_and_exempts_health(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'ratelimit.db').as_posix()}",
            auth_enabled=False,
            rate_limit_enabled=True,
            rate_limit_requests_per_minute=3,
        )
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            for expected_remaining in ("2", "1", "0"):
                res = await ac.get("/api/v1/tracking/shipments")
                assert res.status_code == 200
                assert res.headers["x-ratelimit-limit"] == "3"
                assert res.headers["x-ratelimit-remaining"] == expected_remaining

            blocked = await ac.get("/api/v1/tracking/shipments")
            assert blocked.status_code == 429
            assert int(blocked.headers["retry-after"]) >= 1

            # Health checks remain exempt even when client bucket is exhausted
            assert (await ac.get("/api/v1/health/live")).status_code == 200
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_webhook_outbound_delivery_retries_and_persists_receipt(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'delivery.db').as_posix()}",
            auth_enabled=False,
            rate_limit_enabled=False,
            comm_delivery_mode="webhook",
            carrier_webhook_url="https://carrier.example/webhook",
            delivery_max_retries=3,
        )
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ship_res = await ac.post(
                "/api/v1/tracking/shipments",
                json={
                    "reference_number": "SHP-DLV-1",
                    "bol_number": "BOL-DLV-1",
                    "pro_number": "PRO-DLV-1",
                    "carrier_scac": "ODFL",
                    "carrier_name": "Old Dominion",
                    "origin": "Seattle, WA",
                    "destination": "Denver, CO",
                    "sla_eta": (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
                },
            )
            ship_id = ship_res.json()["id"]

            comm_id = (
                await ac.post(
                    "/api/v1/comms/draft",
                    json={
                        "shipment_id": ship_id,
                        "comm_type": "DETENTION_NOTICE",
                        "channel": "CARRIER_WEBHOOK",
                        "recipient_name": "ODFL Webhook",
                        "recipient_contact": "https://carrier.example/webhook",
                    },
                )
            ).json()["id"]

            await ac.post(
                f"/api/v1/comms/{comm_id}/decision",
                json={"decision": "APPROVED", "actor": "dispatcher"},
            )

            attempts = 0
            captured_headers: dict[str, str] = {}

            class _Resp:
                def __init__(self, code: int, body: dict[str, Any]) -> None:
                    self.status_code = code
                    self._body = body

                def json(self) -> dict[str, Any]:
                    return self._body

            class _FakeClient:
                def __init__(self, *args: Any, **kwargs: Any) -> None:
                    pass

                async def __aenter__(self) -> "_FakeClient":
                    return self

                async def __aexit__(self, *args: Any) -> None:
                    return None

                async def post(self, url: str, **kwargs: Any) -> _Resp:
                    nonlocal attempts
                    attempts += 1
                    captured_headers.update(kwargs.get("headers") or {})
                    if attempts == 1:
                        return _Resp(500, {"error": "transient"})
                    return _Resp(200, {"message_id": "CARRIER-ACK-99"})

            with patch("app.comms.delivery.httpx.AsyncClient", _FakeClient):
                send_res = await ac.post(f"/api/v1/comms/{comm_id}/send")

            assert send_res.status_code == 200
            sent = send_res.json()
            assert sent["status"] == "SENT"
            assert sent["external_message_id"] == "CARRIER-ACK-99"
            assert sent["delivery_attempts"] == 2
            assert sent["delivery_receipt"]["delivery_mode"] == "webhook"
            assert captured_headers["X-Logistics-Signature"].startswith("sha256=")
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_operational_memory_auto_indexing_and_domain_retrieval(client: AsyncClient) -> None:
    ship_res = await client.post(
        "/api/v1/tracking/shipments",
        json={
            "reference_number": "SHP-MEM-1",
            "bol_number": "BOL-MEM-1",
            "pro_number": "PRO-MEM-1",
            "carrier_scac": "BNSF",
            "carrier_name": "BNSF Cold Intermodal",
            "mode": "INTERMODAL",
            "origin": "Los Angeles, CA",
            "destination": "Chicago, IL",
            "sla_eta": (datetime.now(UTC) + timedelta(hours=10)).isoformat(),
            "temperature_controlled": True,
        },
    )
    ship_id = ship_res.json()["id"]

    # Trigger and resolve an exception -> auto-indexes TRACKING_EXCEPTION memory
    ev_res = await client.post(
        f"/api/v1/tracking/shipments/{ship_id}/events",
        json={
            "event_code": "DELAYED",
            "reason_code": "WEATHER",
            "location": "North Platte, NE",
            "reported_eta": (datetime.now(UTC) + timedelta(hours=18)).isoformat(),
        },
    )
    exc_id = ev_res.json()["exception"]["id"]
    res_exc = await client.patch(
        f"/api/v1/tracking/exceptions/{exc_id}",
        json={
            "status": "RESOLVED",
            "resolution_notes": "Re-routed around snow squall via southern siding.",
        },
    )
    assert res_exc.status_code == 200

    search_res = await client.get("/api/v1/memory/search?q=BNSF+Chicago+snow+squall")
    assert search_res.status_code == 200
    hits = search_res.json()
    assert len(hits) >= 1
    assert hits[0]["memory"]["category"] == "TRACKING_EXCEPTION"

    # Route optimize & comm draft consume retrieved memories
    await client.post(
        "/api/v1/routing/lanes",
        json={
            "carrier_scac": "BNSF",
            "carrier_name": "BNSF Cold Intermodal",
            "origin_region": "Los Angeles, CA",
            "destination_region": "Chicago, IL",
            "mode": "INTERMODAL",
            "base_rate_usd": 2490.0,
            "transit_hours": 54,
            "supports_reefer": True,
        },
    )
    opt_res = await client.post(
        "/api/v1/routing/optimize",
        json={"shipment_id": ship_id, "objective": "BALANCED"},
    )
    assert opt_res.status_code == 201
    assert "Operational memory context" in opt_res.json()["rationale"]

    draft_res = await client.post(
        "/api/v1/comms/draft",
        json={
            "shipment_id": ship_id,
            "comm_type": "DELAY_ESCALATION",
            "recipient_name": "BNSF Desk",
            "recipient_contact": "desk@bnsf-example.com",
        },
    )
    assert draft_res.status_code == 201
    assert len(draft_res.json()["grounding_facts"]["historical_context"]) >= 1


@pytest.mark.asyncio
async def test_workers_sla_sweep_and_edi214_batch(client: AsyncClient) -> None:
    past_eta = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    ship_res = await client.post(
        "/api/v1/tracking/shipments",
        json={
            "reference_number": "SHP-WRK-1",
            "bol_number": "BOL-WRK-1",
            "pro_number": "PRO-WRK-1",
            "carrier_scac": "SEFL",
            "carrier_name": "Southeastern Freight",
            "origin": "Savannah, GA",
            "destination": "Atlanta, GA",
            "sla_eta": past_eta,
            "current_eta": past_eta,
        },
    )
    assert ship_res.status_code == 201

    sweep_res = await client.post("/api/v1/workers/sla-sweep")
    assert sweep_res.status_code == 200
    sweep = sweep_res.json()["summary"]
    assert sweep["breached_shipments"] >= 1
    assert sweep["exceptions_opened_or_updated"] >= 1

    excs = (await client.get("/api/v1/tracking/exceptions")).json()
    assert any(item["exception_type"] == "ETA_SLIP" for item in excs)

    batch_res = await client.post(
        "/api/v1/workers/edi214-batch",
        json={
            "payloads": [
                "B10*PRO-WRK-1*BOL-WRK-1*SEFL~AT7*AF*NS***20261126*1000~MS1*MACON*GA*US~",
                "INVALID*EDI*PAYLOAD",
            ]
        },
    )
    assert batch_res.status_code == 200
    summary = batch_res.json()["summary"]
    assert summary["total"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
