"""Initial schema for AI Logistics Coordinator.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-24 18:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("previous_state", sa.String(length=64), nullable=True),
        sa.Column("new_state", sa.String(length=64), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sequence_number"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_sequence_number", "audit_logs", ["sequence_number"])

    op.create_table(
        "shipments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reference_number", sa.String(length=64), nullable=False),
        sa.Column("bol_number", sa.String(length=64), nullable=False),
        sa.Column("pro_number", sa.String(length=64), nullable=False),
        sa.Column("carrier_scac", sa.String(length=16), nullable=False),
        sa.Column("carrier_name", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=128), nullable=False),
        sa.Column("destination", sa.String(length=128), nullable=False),
        sa.Column("last_location", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sla_eta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_eta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False),
        sa.Column("weight_lbs", sa.Float(), nullable=False),
        sa.Column("temperature_controlled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_number"),
    )
    op.create_index("ix_shipments_bol_number", "shipments", ["bol_number"])
    op.create_index("ix_shipments_carrier_scac", "shipments", ["carrier_scac"])
    op.create_index("ix_shipments_pro_number", "shipments", ["pro_number"])
    op.create_index("ix_shipments_reference_number", "shipments", ["reference_number"])
    op.create_index("ix_shipments_status", "shipments", ["status"])

    op.create_table(
        "tracking_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shipment_id", sa.String(length=36), nullable=False),
        sa.Column("source_format", sa.String(length=32), nullable=False),
        sa.Column("raw_code", sa.String(length=64), nullable=False),
        sa.Column("normalized_status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=128), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reported_eta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tracking_events_shipment_id", "tracking_events", ["shipment_id"])

    op.create_table(
        "tracking_exceptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shipment_id", sa.String(length=36), nullable=False),
        sa.Column("exception_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tracking_exceptions_severity", "tracking_exceptions", ["severity"])
    op.create_index(
        "ix_tracking_exceptions_shipment_id", "tracking_exceptions", ["shipment_id"]
    )
    op.create_index("ix_tracking_exceptions_status", "tracking_exceptions", ["status"])

    op.create_table(
        "carrier_lanes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("carrier_scac", sa.String(length=16), nullable=False),
        sa.Column("carrier_name", sa.String(length=128), nullable=False),
        sa.Column("origin_region", sa.String(length=128), nullable=False),
        sa.Column("destination_region", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("base_rate_usd", sa.Float(), nullable=False),
        sa.Column("fuel_surcharge_pct", sa.Float(), nullable=False),
        sa.Column("transit_hours", sa.Integer(), nullable=False),
        sa.Column("on_time_rate", sa.Float(), nullable=False),
        sa.Column("carbon_kg_per_ton_mile", sa.Float(), nullable=False),
        sa.Column("supports_reefer", sa.Boolean(), nullable=False),
        sa.Column("max_weight_lbs", sa.Float(), nullable=False),
        sa.Column("disruption_risk_score", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carrier_lanes_carrier_scac", "carrier_lanes", ["carrier_scac"])
    op.create_index(
        "ix_carrier_lanes_destination_region", "carrier_lanes", ["destination_region"]
    )
    op.create_index("ix_carrier_lanes_origin_region", "carrier_lanes", ["origin_region"])

    op.create_table(
        "disruption_alerts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("disruption_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("added_transit_hours", sa.Integer(), nullable=False),
        sa.Column("cost_surcharge_pct", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_disruption_alerts_region", "disruption_alerts", ["region"])

    op.create_table(
        "route_recommendations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shipment_id", sa.String(length=36), nullable=True),
        sa.Column("origin_region", sa.String(length=128), nullable=False),
        sa.Column("destination_region", sa.String(length=128), nullable=False),
        sa.Column("objective", sa.String(length=32), nullable=False),
        sa.Column("recommended_lane_id", sa.String(length=36), nullable=False),
        sa.Column("recommended_carrier_scac", sa.String(length=16), nullable=False),
        sa.Column("recommended_carrier_name", sa.String(length=128), nullable=False),
        sa.Column("recommended_mode", sa.String(length=32), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("estimated_transit_hours", sa.Integer(), nullable=False),
        sa.Column("estimated_reliability", sa.Float(), nullable=False),
        sa.Column("estimated_carbon_kg", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("alternatives_json", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recommended_lane_id"], ["carrier_lanes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_route_recommendations_shipment_id", "route_recommendations", ["shipment_id"]
    )
    op.create_index("ix_route_recommendations_status", "route_recommendations", ["status"])

    op.create_table(
        "carrier_communications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shipment_id", sa.String(length=36), nullable=False),
        sa.Column("comm_type", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient_name", sa.String(length=128), nullable=False),
        sa.Column("recipient_contact", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("grounding_facts_json", sa.Text(), nullable=False),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("llm_model", sa.String(length=64), nullable=False),
        sa.Column("pii_redacted", sa.Boolean(), nullable=False),
        sa.Column("redacted_categories_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_carrier_communications_shipment_id", "carrier_communications", ["shipment_id"]
    )
    op.create_index("ix_carrier_communications_status", "carrier_communications", ["status"])

    op.create_table(
        "inventory_reconciliations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shipment_id", sa.String(length=36), nullable=True),
        sa.Column("asn_number", sa.String(length=64), nullable=False),
        sa.Column("bol_number", sa.String(length=64), nullable=False),
        sa.Column("warehouse_code", sa.String(length=32), nullable=False),
        sa.Column("expected_total_units", sa.Integer(), nullable=False),
        sa.Column("received_total_units", sa.Integer(), nullable=False),
        sa.Column("damaged_total_units", sa.Integer(), nullable=False),
        sa.Column("variance_units", sa.Integer(), nullable=False),
        sa.Column("shrinkage_pct", sa.Float(), nullable=False),
        sa.Column("financial_impact_usd", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("discrepancies_json", sa.Text(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=False),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("reconciled_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_reconciliations_asn_number", "inventory_reconciliations", ["asn_number"]
    )
    op.create_index(
        "ix_inventory_reconciliations_bol_number", "inventory_reconciliations", ["bol_number"]
    )
    op.create_index(
        "ix_inventory_reconciliations_shipment_id", "inventory_reconciliations", ["shipment_id"]
    )
    op.create_index(
        "ix_inventory_reconciliations_status", "inventory_reconciliations", ["status"]
    )
    op.create_index(
        "ix_inventory_reconciliations_warehouse_code",
        "inventory_reconciliations",
        ["warehouse_code"],
    )

    op.create_table(
        "inventory_alerts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reconciliation_id", sa.String(length=36), nullable=False),
        sa.Column("shipment_id", sa.String(length=36), nullable=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("expected_qty", sa.Integer(), nullable=False),
        sa.Column("received_qty", sa.Integer(), nullable=False),
        sa.Column("damaged_qty", sa.Integer(), nullable=False),
        sa.Column("variance_qty", sa.Integer(), nullable=False),
        sa.Column("financial_impact_usd", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["reconciliation_id"], ["inventory_reconciliations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_alerts_reconciliation_id", "inventory_alerts", ["reconciliation_id"]
    )
    op.create_index("ix_inventory_alerts_severity", "inventory_alerts", ["severity"])
    op.create_index("ix_inventory_alerts_shipment_id", "inventory_alerts", ["shipment_id"])
    op.create_index("ix_inventory_alerts_sku", "inventory_alerts", ["sku"])
    op.create_index("ix_inventory_alerts_status", "inventory_alerts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_inventory_alerts_status", table_name="inventory_alerts")
    op.drop_index("ix_inventory_alerts_sku", table_name="inventory_alerts")
    op.drop_index("ix_inventory_alerts_shipment_id", table_name="inventory_alerts")
    op.drop_index("ix_inventory_alerts_severity", table_name="inventory_alerts")
    op.drop_index("ix_inventory_alerts_reconciliation_id", table_name="inventory_alerts")
    op.drop_table("inventory_alerts")

    op.drop_index("ix_inventory_reconciliations_warehouse_code", table_name="inventory_reconciliations")
    op.drop_index("ix_inventory_reconciliations_status", table_name="inventory_reconciliations")
    op.drop_index("ix_inventory_reconciliations_shipment_id", table_name="inventory_reconciliations")
    op.drop_index("ix_inventory_reconciliations_bol_number", table_name="inventory_reconciliations")
    op.drop_index("ix_inventory_reconciliations_asn_number", table_name="inventory_reconciliations")
    op.drop_table("inventory_reconciliations")

    op.drop_index("ix_carrier_communications_status", table_name="carrier_communications")
    op.drop_index("ix_carrier_communications_shipment_id", table_name="carrier_communications")
    op.drop_table("carrier_communications")

    op.drop_index("ix_route_recommendations_status", table_name="route_recommendations")
    op.drop_index("ix_route_recommendations_shipment_id", table_name="route_recommendations")
    op.drop_table("route_recommendations")

    op.drop_index("ix_disruption_alerts_region", table_name="disruption_alerts")
    op.drop_table("disruption_alerts")

    op.drop_index("ix_carrier_lanes_origin_region", table_name="carrier_lanes")
    op.drop_index("ix_carrier_lanes_destination_region", table_name="carrier_lanes")
    op.drop_index("ix_carrier_lanes_carrier_scac", table_name="carrier_lanes")
    op.drop_table("carrier_lanes")

    op.drop_index("ix_tracking_exceptions_status", table_name="tracking_exceptions")
    op.drop_index("ix_tracking_exceptions_shipment_id", table_name="tracking_exceptions")
    op.drop_index("ix_tracking_exceptions_severity", table_name="tracking_exceptions")
    op.drop_table("tracking_exceptions")

    op.drop_index("ix_tracking_events_shipment_id", table_name="tracking_events")
    op.drop_table("tracking_events")

    op.drop_index("ix_shipments_status", table_name="shipments")
    op.drop_index("ix_shipments_reference_number", table_name="shipments")
    op.drop_index("ix_shipments_pro_number", table_name="shipments")
    op.drop_index("ix_shipments_carrier_scac", table_name="shipments")
    op.drop_index("ix_shipments_bol_number", table_name="shipments")
    op.drop_table("shipments")

    op.drop_index("ix_audit_logs_sequence_number", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
