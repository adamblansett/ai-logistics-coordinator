from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comms.schemas import CommDraftRequest
from app.comms.service import draft_communication
from app.core.audit import record_audit_event
from app.db.base import utcnow
from app.inventory.schemas import ExpectedLineItem, ReceivedLineItem, ReconciliationCreate
from app.inventory.service import run_reconciliation
from app.llm.router import LLMRouter
from app.routing.schemas import CarrierLaneCreate, DisruptionAlertCreate, RouteOptimizeRequest
from app.routing.service import create_disruption, create_lane, optimize_route
from app.tracking.models import Shipment
from app.tracking.normalizer import normalize_webhook_event, parse_edi_214
from app.tracking.schemas import ShipmentCreate, WebhookEventCreate
from app.tracking.service import create_shipment, ingest_event


async def seed_demo_workspace(
    session: AsyncSession,
    llm_router: LLMRouter,
) -> dict[str, Any]:
    """Idempotently populate a realistic end-to-end logistics scenario for Phase 1 evaluation."""
    existing = await session.execute(select(Shipment.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return {
            "seeded": False,
            "message": "Workspace already contains data.",
            "counts": {},
        }

    now = utcnow()

    # 1. Create 5 realistic shipments across corridors and modes
    ship1 = await create_shipment(
        session,
        ShipmentCreate(
            reference_number="SHP-2026-1001",
            bol_number="BOL-9011001",
            pro_number="PRO-7701",
            carrier_scac="CRST",
            carrier_name="CrestLine Cold Chain",
            mode="FTL",
            origin="Los Angeles, CA",
            destination="Chicago, IL",
            last_location="Los Angeles, CA",
            sla_eta=now + timedelta(hours=14),
            weight_lbs=34500.0,
            temperature_controlled=True,
            actor="demo-seed",
        ),
    )
    ship2 = await create_shipment(
        session,
        ShipmentCreate(
            reference_number="SHP-2026-1002",
            bol_number="BOL-9011002",
            pro_number="PRO-7702",
            carrier_scac="SEFL",
            carrier_name="Southeastern Intermodal",
            mode="INTERMODAL",
            origin="Savannah, GA",
            destination="Atlanta, GA",
            last_location="Savannah Terminal, GA",
            sla_eta=now + timedelta(hours=6),
            weight_lbs=28000.0,
            temperature_controlled=False,
            actor="demo-seed",
        ),
    )
    ship3 = await create_shipment(
        session,
        ShipmentCreate(
            reference_number="SHP-2026-1003",
            bol_number="BOL-9011003",
            pro_number="PRO-7703",
            carrier_scac="JBHT",
            carrier_name="J.B. Hunt Transport",
            mode="FTL",
            origin="Dallas, TX",
            destination="Newark, NJ",
            last_location="Knoxville, TN",
            sla_eta=now + timedelta(hours=18),
            weight_lbs=38200.0,
            temperature_controlled=False,
            actor="demo-seed",
        ),
    )
    ship4 = await create_shipment(
        session,
        ShipmentCreate(
            reference_number="SHP-2026-1004",
            bol_number="BOL-9011004",
            pro_number="PRO-7704",
            carrier_scac="ODFL",
            carrier_name="Old Dominion Freight Line",
            mode="LTL",
            origin="Seattle, WA",
            destination="Denver, CO",
            last_location="Boise Cross-Dock, ID",
            sla_eta=now + timedelta(hours=8),
            weight_lbs=12400.0,
            temperature_controlled=False,
            actor="demo-seed",
        ),
    )
    ship5 = await create_shipment(
        session,
        ShipmentCreate(
            reference_number="SHP-2026-1005",
            bol_number="BOL-9011005",
            pro_number="PRO-7705",
            carrier_scac="KNIG",
            carrier_name="Knight-Swift Border Express",
            mode="FTL",
            origin="Laredo, TX",
            destination="Detroit, MI",
            last_location="Laredo Port of Entry, TX",
            sla_eta=now + timedelta(hours=22),
            weight_lbs=31000.0,
            temperature_controlled=False,
            actor="demo-seed",
        ),
    )

    # 2. Ingest EDI 214 & Webhook events to simulate realistic live exceptions
    edi_eta_str = (now + timedelta(hours=23)).strftime("%Y%m%d")
    edi_date_str = now.strftime("%Y%m%d")
    edi_payload = (
        f"B10*PRO-7701*BOL-9011001*CRST~"
        f"AT7**NS*SD*BG*{edi_date_str}*0915~"
        f"MS1*NORTH PLATTE*NE*US~"
        f"G62*17*{edi_eta_str}~"
    )
    _, ship1, _ = await ingest_event(
        session,
        ship1,
        parse_edi_214(edi_payload),
        raw_payload={"raw_edi_214": edi_payload},
        actor="edi-gateway",
    )

    _, ship2, _ = await ingest_event(
        session,
        ship2,
        normalize_webhook_event(
            WebhookEventCreate(
                event_code="PORT_CONGESTION",
                location="Garden City Terminal, Savannah, GA",
                reported_eta=now + timedelta(hours=11),
                notes="Cranes backed up; chassis turn time elevated by 5 hours.",
                actor="port-telemetry",
            )
        ),
        raw_payload={"event_code": "PORT_CONGESTION"},
        actor="port-telemetry",
    )

    _, ship3, _ = await ingest_event(
        session,
        ship3,
        normalize_webhook_event(
            WebhookEventCreate(
                event_code="IN_TRANSIT",
                location="Knoxville, TN",
                reported_eta=now + timedelta(hours=17),
                notes="Clearing I-81 corridor on schedule.",
                actor="eld-webhook",
            )
        ),
        raw_payload={"event_code": "IN_TRANSIT"},
        actor="eld-webhook",
    )

    _, ship4, _ = await ingest_event(
        session,
        ship4,
        normalize_webhook_event(
            WebhookEventCreate(
                event_code="DETENTION",
                location="Boise Cross-Dock, ID",
                reported_eta=now + timedelta(hours=11),
                notes="Driver detained 180 minutes awaiting dock door release.",
                actor="dock-gate-api",
            )
        ),
        raw_payload={"event_code": "DETENTION"},
        actor="dock-gate-api",
    )

    _, ship5, _ = await ingest_event(
        session,
        ship5,
        normalize_webhook_event(
            WebhookEventCreate(
                event_code="CUSTOMS_HOLD",
                location="Laredo Port of Entry, TX",
                reported_eta=now + timedelta(hours=29),
                notes="CBP secondary manifest inspection pending broker commercial invoice.",
                actor="customs-broker-feed",
            )
        ),
        raw_payload={"event_code": "CUSTOMS_HOLD"},
        actor="customs-broker-feed",
    )

    # 3. Create 6 Carrier Lanes across active corridors
    await create_lane(
        session,
        CarrierLaneCreate(
            carrier_scac="CRST",
            carrier_name="CrestLine Cold Chain",
            origin_region="Los Angeles, CA",
            destination_region="Chicago, IL",
            mode="FTL",
            base_rate_usd=3250.0,
            fuel_surcharge_pct=14.0,
            transit_hours=42,
            on_time_rate=0.92,
            carbon_kg_per_ton_mile=0.16,
            supports_reefer=True,
            max_weight_lbs=44000.0,
            disruption_risk_score=0.22,
            actor="demo-seed",
        ),
    )
    await create_lane(
        session,
        CarrierLaneCreate(
            carrier_scac="BNSF",
            carrier_name="BNSF Cold Intermodal",
            origin_region="Los Angeles, CA",
            destination_region="Chicago, IL",
            mode="INTERMODAL",
            base_rate_usd=2490.0,
            fuel_surcharge_pct=9.0,
            transit_hours=56,
            on_time_rate=0.96,
            carbon_kg_per_ton_mile=0.06,
            supports_reefer=True,
            max_weight_lbs=44000.0,
            disruption_risk_score=0.08,
            actor="demo-seed",
        ),
    )
    await create_lane(
        session,
        CarrierLaneCreate(
            carrier_scac="FXFE",
            carrier_name="FedEx Custom Critical Reefer",
            origin_region="Los Angeles, CA",
            destination_region="Chicago, IL",
            mode="AIR",
            base_rate_usd=5400.0,
            fuel_surcharge_pct=18.0,
            transit_hours=14,
            on_time_rate=0.985,
            carbon_kg_per_ton_mile=0.52,
            supports_reefer=True,
            max_weight_lbs=40000.0,
            disruption_risk_score=0.04,
            actor="demo-seed",
        ),
    )
    await create_lane(
        session,
        CarrierLaneCreate(
            carrier_scac="SEFL",
            carrier_name="Southeastern Intermodal",
            origin_region="Savannah, GA",
            destination_region="Atlanta, GA",
            mode="INTERMODAL",
            base_rate_usd=890.0,
            fuel_surcharge_pct=11.0,
            transit_hours=10,
            on_time_rate=0.91,
            carbon_kg_per_ton_mile=0.07,
            supports_reefer=False,
            max_weight_lbs=44000.0,
            disruption_risk_score=0.18,
            actor="demo-seed",
        ),
    )
    await create_lane(
        session,
        CarrierLaneCreate(
            carrier_scac="SAIA",
            carrier_name="Saia Direct Regional",
            origin_region="Savannah, GA",
            destination_region="Atlanta, GA",
            mode="FTL",
            base_rate_usd=1120.0,
            fuel_surcharge_pct=13.0,
            transit_hours=5,
            on_time_rate=0.97,
            carbon_kg_per_ton_mile=0.15,
            supports_reefer=True,
            max_weight_lbs=45000.0,
            disruption_risk_score=0.06,
            actor="demo-seed",
        ),
    )
    await create_lane(
        session,
        CarrierLaneCreate(
            carrier_scac="RYDR",
            carrier_name="Ryder Border Expedite",
            origin_region="Laredo, TX",
            destination_region="Detroit, MI",
            mode="FTL",
            base_rate_usd=2850.0,
            fuel_surcharge_pct=13.0,
            transit_hours=28,
            on_time_rate=0.95,
            carbon_kg_per_ton_mile=0.15,
            supports_reefer=False,
            max_weight_lbs=44000.0,
            disruption_risk_score=0.10,
            actor="demo-seed",
        ),
    )

    # 4. Active Disruption Alerts
    await create_disruption(
        session,
        DisruptionAlertCreate(
            region="Chicago, IL",
            disruption_type="WEATHER",
            severity="HIGH",
            added_transit_hours=8,
            cost_surcharge_pct=6.5,
            description="Lake-effect snow advisory along I-80/I-55 freight approaches.",
            active=True,
            actor="demo-seed",
        ),
    )
    await create_disruption(
        session,
        DisruptionAlertCreate(
            region="Savannah, GA",
            disruption_type="PORT_CONGESTION",
            severity="MEDIUM",
            added_transit_hours=5,
            cost_surcharge_pct=4.0,
            description="Container dwell backlog at Garden City berth gates.",
            active=True,
            actor="demo-seed",
        ),
    )

    # 5. Pending Route Recommendation
    await optimize_route(
        session,
        llm_router,
        RouteOptimizeRequest(
            shipment_id=ship1.id,
            objective="BALANCED",
            actor="demo-seed",
        ),
    )

    # 6. Pending Carrier Communication Drafts (Human-in-the-loop sign-off)
    await draft_communication(
        session,
        llm_router,
        CommDraftRequest(
            shipment_id=ship4.id,
            comm_type="DETENTION_NOTICE",
            channel="EMAIL",
            recipient_name="ODFL Boise Terminal Dispatch",
            recipient_contact="dispatch.boise@odfl-example.com",
            custom_notes="Verify gate arrival 06:15 MST and confirm detention clock waiver.",
            actor="demo-seed",
        ),
    )
    await draft_communication(
        session,
        llm_router,
        CommDraftRequest(
            shipment_id=ship1.id,
            comm_type="DELAY_ESCALATION",
            channel="EDI_PORTAL",
            recipient_name="CrestLine Midwest Control Desk",
            recipient_contact="midwest.ops@crestline-example.com",
            custom_notes="Maintain reefer setpoint 34F and confirm revised dock appointment.",
            actor="demo-seed",
        ),
    )

    # 7. Inventory Reconciliations (1 clean match, 1 shortage + damage discrepancy)
    await run_reconciliation(
        session,
        llm_router,
        ReconciliationCreate(
            shipment_id=ship3.id,
            asn_number="ASN-440910",
            bol_number=ship3.bol_number,
            warehouse_code="EWR-DC2",
            expected_lines=[
                ExpectedLineItem(
                    sku="SKU-MED-101",
                    description="Sterile Packaging Cartons",
                    expected_qty=240,
                    unit_cost_usd=28.5,
                ),
                ExpectedLineItem(
                    sku="SKU-MED-204",
                    description="Thermal Sensor Pallets",
                    expected_qty=120,
                    unit_cost_usd=45.0,
                ),
            ],
            received_lines=[
                ReceivedLineItem(sku="SKU-MED-101", received_qty=240, damaged_qty=0),
                ReceivedLineItem(sku="SKU-MED-204", received_qty=120, damaged_qty=0),
            ],
            actor="demo-seed",
        ),
    )
    await run_reconciliation(
        session,
        llm_router,
        ReconciliationCreate(
            shipment_id=ship2.id,
            asn_number="ASN-440918",
            bol_number=ship2.bol_number,
            warehouse_code="ATL-FC1",
            expected_lines=[
                ExpectedLineItem(
                    sku="SKU-IND-880",
                    description="Precision Hydraulic Valves",
                    expected_qty=100,
                    unit_cost_usd=185.0,
                ),
                ExpectedLineItem(
                    sku="SKU-IND-912",
                    description="Servo Actuator Assemblies",
                    expected_qty=50,
                    unit_cost_usd=310.0,
                ),
            ],
            received_lines=[
                ReceivedLineItem(sku="SKU-IND-880", received_qty=88, damaged_qty=3),
                ReceivedLineItem(sku="SKU-IND-912", received_qty=50, damaged_qty=0),
            ],
            actor="demo-seed",
        ),
    )

    await record_audit_event(
        session,
        entity_type="system",
        entity_id="workspace",
        action="DEMO_SEEDED",
        actor="demo-seed",
        previous_state="EMPTY",
        new_state="POPULATED",
        details={"shipments": 5, "lanes": 6, "disruptions": 2, "reconciliations": 2},
    )
    await session.commit()

    return {
        "seeded": True,
        "message": "Seeded realistic Phase 1 logistics coordination workspace.",
        "counts": {
            "shipments": 5,
            "carrier_lanes": 6,
            "disruptions": 2,
            "route_recommendations": 1,
            "carrier_communications": 2,
            "inventory_reconciliations": 2,
        },
    }
