"""Create player_profiles, cube_transactions, and player_cards tables.

Revision ID: 012_player_profiles_inventory
Revises: 011_locations_full
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012_player_profiles_inventory"
down_revision: str | None = "011_locations_full"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea las tablas de perfil de jugador, historial de cubos e inventario de cartas."""
    # 1. Perfil de jugador
    op.create_table(
        "player_profiles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("elo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cubes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "has_received_initial_collection",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("cubes >= 0", name="ck_player_profiles_cubes_positive"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_player_profiles_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_player_profiles"),
    )

    # 2. Historial de transacciones de cubos (Ledger inmutable - RNF-INT-03)
    op.create_table(
        "cube_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "balance_after >= 0", name="ck_cube_transactions_balance_positive"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_cube_transactions_user_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cube_transactions"),
    )
    op.create_index(
        "ix_cube_transactions_user_created",
        "cube_transactions",
        ["user_id", "created_at"],
    )

    # 3. Inventario transaccional de cartas de jugadores
    op.create_table(
        "player_cards",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("card_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_player_cards_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_player_cards_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["catalog_cards.id"],
            name="fk_player_cards_card_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", "card_id", name="pk_player_cards"),
    )


def downgrade() -> None:
    """Revierte las tablas creadas en orden inverso."""
    op.drop_table("player_cards")
    op.drop_index("ix_cube_transactions_user_created", table_name="cube_transactions")
    op.drop_table("cube_transactions")
    op.drop_table("player_profiles")
