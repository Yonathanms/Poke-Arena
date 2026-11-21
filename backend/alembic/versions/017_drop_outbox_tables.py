"""Elimina tablas outbox, legadas y de idempotencia duplicada, y conecta contadores.

Tablas eliminadas:
- shared_outbox y outbox_events: reemplazadas por escritura directa SQL -> MongoDB
  y el reconciliador periódico centralizado en la API principal.
- catalog_cards_legacy_002 y catalog_card_migration_issues: residuos históricos de 002.
- catalog_locations: tabla inicial obsoleta reemplazada por locations (011).
- idempotency_records: duplicada de shared_idempotency_records (unificada).

Relación añadida:
- FK catalog_card_code_counters(card_type) -> catalog_card_types(code).

Revision ID: 017_drop_outbox_tables
Revises: 016_card_types_and_rarities
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017_drop_outbox_tables"
down_revision: str | None = "016_card_types_and_rarities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Elimina tablas obsoletas/duplicadas y conecta catalog_card_code_counters."""
    op.execute("DROP TABLE IF EXISTS public.shared_outbox CASCADE")
    op.execute("DROP TABLE IF EXISTS public.outbox_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.catalog_cards_legacy_002 CASCADE")
    op.execute("DROP TABLE IF EXISTS public.catalog_card_migration_issues CASCADE")
    op.execute("DROP TABLE IF EXISTS public.catalog_locations CASCADE")
    op.execute("DROP TABLE IF EXISTS public.idempotency_records CASCADE")

    op.create_foreign_key(
        "fk_catalog_card_code_counters_card_type",
        "catalog_card_code_counters",
        "catalog_card_types",
        ["card_type"],
        ["code"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Revierte la FK de contadores y recrea las tablas eliminadas."""
    op.drop_constraint(
        "fk_catalog_card_code_counters_card_type",
        "catalog_card_code_counters",
        type_="foreignkey",
    )

    op.create_table(
        "catalog_card_migration_issues",
        sa.Column("legacy_card_id", sa.String(length=36), nullable=False),
        sa.Column("legacy_code", sa.String(length=30), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("legacy_card_id"),
    )
    op.create_table(
        "shared_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aggregate_type", sa.String(length=60), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sanitized_error", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id", name="shared_outbox_pkey"),
        sa.UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_shared_outbox_aggregate_version",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_shared_outbox_attempts"),
    )
    op.create_index("ix_shared_outbox_event_type", "shared_outbox", ["event_type"])
    op.create_index("ix_shared_outbox_status", "shared_outbox", ["status"])
    op.create_index(
        "ix_shared_outbox_claim",
        "shared_outbox",
        ["status", "next_attempt_at", "lease_expires_at", "created_at"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evento", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])

    op.create_table(
        "catalog_cards_legacy_002",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("power", sa.Integer(), nullable=False),
        sa.Column("card_type", sa.String(length=10), nullable=False),
        sa.Column("rarity", sa.String(length=20), nullable=False),
        sa.Column("image_url", sa.String(length=255), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=255), nullable=True),
        sa.Column("ability_spec", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "catalog_locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("image_url", sa.String(length=255), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=255), nullable=True),
        sa.Column("effect_spec", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
