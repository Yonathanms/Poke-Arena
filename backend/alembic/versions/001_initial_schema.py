"""initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-23 22:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tabla de Cartas (catalog_cards)
    op.create_table(
        "catalog_cards",
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
    op.create_index(op.f("ix_catalog_cards_code"), "catalog_cards", ["code"], unique=True)
    op.create_index(
        op.f("ix_catalog_cards_card_type"), "catalog_cards", ["card_type"], unique=False
    )
    op.create_index(op.f("ix_catalog_cards_rarity"), "catalog_cards", ["rarity"], unique=False)

    # 2. Tabla de Ubicaciones (catalog_locations)
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

    # 3. Tabla Transactional Outbox (shared_outbox)
    op.create_table(
        "shared_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_shared_outbox_event_type"), "shared_outbox", ["event_type"], unique=False
    )
    op.create_index(op.f("ix_shared_outbox_status"), "shared_outbox", ["status"], unique=False)

    # 4. Tabla de Idempotencia (shared_idempotency_records)
    op.create_table(
        "shared_idempotency_records",
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=200), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("idempotency_key"),
    )


def downgrade() -> None:
    op.drop_table("shared_idempotency_records")
    op.drop_index(op.f("ix_shared_outbox_status"), table_name="shared_outbox")
    op.drop_index(op.f("ix_shared_outbox_event_type"), table_name="shared_outbox")
    op.drop_table("shared_outbox")
    op.drop_table("catalog_locations")
    op.drop_index(op.f("ix_catalog_cards_rarity"), table_name="catalog_cards")
    op.drop_index(op.f("ix_catalog_cards_card_type"), table_name="catalog_cards")
    op.drop_index(op.f("ix_catalog_cards_code"), table_name="catalog_cards")
    op.drop_table("catalog_cards")
