import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inventory_reconciliation_alerts_and_resolution(client: AsyncClient) -> None:
    # 1. Clean ASN/BOL match
    clean_res = await client.post(
        "/api/v1/inventory/reconcile",
        json={
            "asn_number": "ASN-CLEAN-1",
            "bol_number": "BOL-CLEAN-1",
            "warehouse_code": "ORD-1",
            "expected_lines": [
                {"sku": "SKU-A", "description": "Widget A", "expected_qty": 50, "unit_cost_usd": 20}
            ],
            "received_lines": [{"sku": "SKU-A", "received_qty": 50, "damaged_qty": 0}],
        },
    )
    assert clean_res.status_code == 201
    clean_data = clean_res.json()
    assert clean_data["status"] == "MATCHED"
    assert clean_data["variance_units"] == 0
    assert clean_data["financial_impact_usd"] == 0.0
    assert clean_data["discrepancies"] == []

    # 2. Discrepancy run with shortage, damaged units, and unexpected SKU
    disc_res = await client.post(
        "/api/v1/inventory/reconcile",
        json={
            "asn_number": "ASN-DISC-2",
            "bol_number": "BOL-DISC-2",
            "warehouse_code": "ATL-2",
            "expected_lines": [
                {
                    "sku": "SKU-VALVE",
                    "description": "Hydraulic Valve",
                    "expected_qty": 100,
                    "unit_cost_usd": 200.0,
                }
            ],
            "received_lines": [
                {"sku": "SKU-VALVE", "received_qty": 85, "damaged_qty": 5},
                {
                    "sku": "SKU-EXTRA",
                    "description": "Unlisted Gasket Box",
                    "received_qty": 4,
                    "damaged_qty": 0,
                    "unit_cost_usd": 50.0,
                },
            ],
        },
    )
    assert disc_res.status_code == 201
    disc_data = disc_res.json()
    assert disc_data["status"] == "DISCREPANCY_OPEN"
    # 15 missing * $200 = $3000; 5 damaged * $200 = $1000; 4 unexpected * $50 = $200 -> $4200
    assert disc_data["financial_impact_usd"] == 4200.0
    assert disc_data["shrinkage_pct"] == 20.0
    alert_types = {item["alert_type"] for item in disc_data["discrepancies"]}
    assert alert_types == {"SHORTAGE", "DAMAGED", "UNEXPECTED_SKU"}

    # Fetch alerts for reconciliation and resolve all -> parent reconciliation becomes RESOLVED
    detail_res = await client.get(f"/api/v1/inventory/reconciliations/{disc_data['id']}")
    assert detail_res.status_code == 200
    alerts = detail_res.json()["alerts"]
    assert len(alerts) == 3

    for alert in alerts:
        patch_res = await client.patch(
            f"/api/v1/inventory/alerts/{alert['id']}",
            json={"status": "RESOLVED", "resolution_notes": "Claim settled with carrier"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "RESOLVED"

    final_rec = (await client.get(f"/api/v1/inventory/reconciliations/{disc_data['id']}")).json()
    assert final_rec["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_demo_seed_dashboard_and_audit_chain_tamper_detection(
    test_app: FastAPI,
    client: AsyncClient,
) -> None:
    seed1 = await client.post("/api/v1/demo/seed")
    assert seed1.status_code == 200
    assert seed1.json()["seeded"] is True

    # Idempotent second call
    seed2 = await client.post("/api/v1/demo/seed")
    assert seed2.status_code == 200
    assert seed2.json()["seeded"] is False

    summary_res = await client.get("/api/v1/dashboard/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_shipments"] == 5
    assert summary["open_tracking_exceptions"] >= 4
    assert summary["pending_route_recommendations"] == 1
    assert summary["pending_comm_approvals"] == 2
    assert summary["open_inventory_alerts"] >= 2
    assert summary["total_audit_entries"] > 10

    verify_ok = await client.get("/api/v1/audit/verify")
    assert verify_ok.status_code == 200
    assert verify_ok.json()["valid"] is True
    assert verify_ok.json()["checked_entries"] == summary["total_audit_entries"]

    # Tamper directly with DB row 1 and verify chain catches tampering
    async with test_app.state.session_factory() as session:
        await session.execute(
            text("UPDATE audit_logs SET action = 'TAMPERED' WHERE sequence_number = 1")
        )
        await session.commit()

    verify_bad = await client.get("/api/v1/audit/verify")
    assert verify_bad.status_code == 200
    assert verify_bad.json()["valid"] is False
    assert verify_bad.json()["first_broken_id"] is not None
