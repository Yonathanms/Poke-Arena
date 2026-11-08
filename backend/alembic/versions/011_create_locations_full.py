"""Create locations, outbox_events and idempotency_records tables.

Revision ID: 011_locations_full
Revises: 1g_local_master_admin
Create Date: 2026-11-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011_locations_full"
down_revision = "1g_local_master_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("descripcion", sa.String(length=500), nullable=False),
        sa.Column("card_limit", sa.Integer(), nullable=False),
        sa.Column("energia_tipo", sa.String(length=20), nullable=False),
        sa.Column("energia_valor", sa.Integer(), nullable=False),
        sa.Column("efecto_tipo", sa.String(length=50), nullable=False),
        sa.Column("efecto_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("url_grande", sa.String(length=500), nullable=False),
        sa.Column("url_tablero", sa.String(length=500), nullable=False),
        sa.Column("imagen_grande_id", sa.String(length=255), nullable=True),
        sa.Column("imagen_thumb_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evento", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])

    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_outbox_events_status", "outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("locations")
