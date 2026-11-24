from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_multi_objective_routing_constraints_and_approval(client: AsyncClient) -> None:
    # Create shipment needing reefer from Seattle, WA -> Denver, CO
    ship_res = await client.post(
        "/api/v1/tracking/shipments",
        json={
            "reference_number": "SHP-RTE-100",
            "bol_number": "BOL-RTE-100",
            "pro_number": "PRO-RTE-100",
            "carrier_scac": "OLD1",
            "carrier_name": "Legacy Freight",
            "mode": "FTL",
            "origin": "Seattle, WA",
            "destination": "Denver, CO",
            "sla_eta": (datetime.now(UTC) + timedelta(hours=12)).isoformat(),
            "weight_lbs": 24000,
            "temperature_controlled": True,
        },
    )
    assert ship_res.status_code == 201
    shipment_id = ship_res.json()["id"]

    # Lane 1: Low-cost reefer carrier
    await client.post(
        "/api/v1/routing/lanes",
        json={
            "carrier_scac": "ECON",
            "carrier_name": "Economy Cold FTL",
            "origin_region": "Seattle, WA",
            "destination_region": "Denver, CO",
            "mode": "FTL",
            "base_rate_usd": 1800.0,
            "fuel_surcharge_pct": 10.0,
            "transit_hours": 36,
            "on_time_rate": 0.90,
            "carbon_kg_per_ton_mile": 0.18,
            "supports_reefer": True,
            "max_weight_lbs": 44000,
        },
    )
    # Lane 2: Fast premium reefer air-expedite
    await client.post(
        "/api/v1/routing/lanes",
        json={
            "carrier_scac": "FAST",
            "carrier_name": "Cascade Cold Air",
            "origin_region": "Seattle, WA",
            "destination_region": "Denver, CO",
            "mode": "AIR",
            "base_rate_usd": 4500.0,
            "fuel_surcharge_pct": 15.0,
            "transit_hours": 8,
            "on_time_rate": 0.99,
            "carbon_kg_per_ton_mile": 0.50,
            "supports_reefer": True,
            "max_weight_lbs": 40000,
        },
    )
    # Lane 3: Low-carbon intermodal WITHOUT reefer (must be excluded when reefer=True)
    await client.post(
        "/api/v1/routing/lanes",
        json={
            "carrier_scac": "RAIL",
            "carrier_name": "GreenRail Intermodal",
            "origin_region": "Seattle, WA",
            "destination_region": "Denver, CO",
            "mode": "INTERMODAL",
            "base_rate_usd": 1400.0,
            "fuel_surcharge_pct": 8.0,
            "transit_hours": 48,
            "on_time_rate": 0.94,
            "carbon_kg_per_ton_mile": 0.05,
            "supports_reefer": False,
            "max_weight_lbs": 44000,
        },
    )

    # Add active disruption in Denver adding 4h transit and 5% surcharge
    dis_res = await client.post(
        "/api/v1/routing/disruptions",
        json={
            "region": "Denver, CO",
            "disruption_type": "WEATHER",
            "severity": "MEDIUM",
            "added_transit_hours": 4,
            "cost_surcharge_pct": 5.0,
            "description": "I-70 mountain pass snow chain advisory",
        },
    )
    assert dis_res.status_code == 201

    # 1. LOWEST_COST for reefer shipment -> ECON wins, RAIL excluded by reefer constraint
    cost_rec = await client.post(
        "/api/v1/routing/optimize",
        json={"shipment_id": shipment_id, "objective": "LOWEST_COST"},
    )
    assert cost_rec.status_code == 201
    cost_data = cost_rec.json()
    assert cost_data["recommended_carrier_scac"] == "ECON"
    assert cost_data["estimated_transit_hours"] == 40  # 36 + 4 disruption hours
    assert all(alt["carrier_scac"] != "RAIL" for alt in cost_data["alternatives"])

    # 2. FASTEST_TRANSIT for reefer shipment -> FAST wins
    fast_rec = await client.post(
        "/api/v1/routing/optimize",
        json={"shipment_id": shipment_id, "objective": "FASTEST_TRANSIT"},
    )
    assert fast_rec.status_code == 201
    fast_data = fast_rec.json()
    assert fast_data["recommended_carrier_scac"] == "FAST"
    assert fast_data["estimated_transit_hours"] == 12  # 8 + 4 disruption hours

    # 3. LOWEST_CARBON without reefer constraint -> RAIL wins
    eco_rec = await client.post(
        "/api/v1/routing/optimize",
        json={
            "origin_region": "Seattle, WA",
            "destination_region": "Denver, CO",
            "weight_lbs": 24000,
            "temperature_controlled": False,
            "objective": "LOWEST_CARBON",
        },
    )
    assert eco_rec.status_code == 201
    assert eco_rec.json()["recommended_carrier_scac"] == "RAIL"

    # 4. Approve FAST recommendation -> updates shipment carrier & rejects double-decision
    approve_res = await client.post(
        f"/api/v1/routing/recommendations/{fast_data['id']}/decision",
        json={"decision": "APPROVED", "actor": "senior-dispatcher", "notes": "Protect cold chain"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    updated_ship = (await client.get(f"/api/v1/tracking/shipments/{shipment_id}")).json()
    assert updated_ship["carrier_scac"] == "FAST"
    assert updated_ship["mode"] == "AIR"

    double_res = await client.post(
        f"/api/v1/routing/recommendations/{fast_data['id']}/decision",
        json={"decision": "REJECTED", "actor": "senior-dispatcher"},
    )
    assert double_res.status_code == 409
