"""Phase 2 auth users, operational memories, and communication delivery receipts.

Revision ID: 0002_phase2_auth_memory_delivery
Revises: 0001_initial_schema
Create Date: 2026-11-26 07:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase2_auth_memory_delivery"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "operational_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("corridor", sa.String(length=128), nullable=True),
        sa.Column("carrier_scac", sa.String(length=16), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_memories_carrier_scac", "operational_memories", ["carrier_scac"]
    )
    op.create_index("ix_operational_memories_category", "operational_memories", ["category"])
    op.create_index("ix_operational_memories_corridor", "operational_memories", ["corridor"])
    op.create_index("ix_operational_memories_entity_id", "operational_memories", ["entity_id"])

    with op.batch_alter_table("carrier_communications") as batch_op:
        batch_op.add_column(
            sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("delivery_receipt_json", sa.Text(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("carrier_communications") as batch_op:
        batch_op.drop_column("delivery_receipt_json")
        batch_op.drop_column("delivery_attempts")

    op.drop_index("ix_operational_memories_entity_id", table_name="operational_memories")
    op.drop_index("ix_operational_memories_corridor", table_name="operational_memories")
    op.drop_index("ix_operational_memories_category", table_name="operational_memories")
    op.drop_index("ix_operational_memories_carrier_scac", table_name="operational_memories")
    op.drop_table("operational_memories")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
