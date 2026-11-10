"""Crea las tablas de decks del jugador.

Revision ID: 015_player_decks
Revises: 014_identity_account_immutable
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015_player_decks"
down_revision: str | None = "014_identity_account_immutable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea player_decks y player_deck_cards con sus índices y permisos."""
    op.create_table(
        "player_decks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_player_decks_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_player_decks"),
        sa.UniqueConstraint("user_id", "name", name="uq_player_deck_name"),
    )
    op.create_index("ix_player_decks_user_id", "player_decks", ["user_id"])

    op.create_table(
        "player_deck_cards",
        sa.Column("deck_id", sa.String(length=36), nullable=False),
        sa.Column("card_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["deck_id"],
            ["player_decks.id"],
            name="fk_player_deck_cards_deck_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["catalog_cards.id"],
            name="fk_player_deck_cards_card_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("deck_id", "card_id", name="pk_player_deck_cards"),
    )
    op.create_index("ix_player_deck_cards_deck_id", "player_deck_cards", ["deck_id"])

    op.execute("""
        DO $$
        DECLARE rol_aplicacion name;
        BEGIN
            FOR rol_aplicacion IN
                SELECT rolname FROM pg_roles WHERE rolname IN ('orm_media_test', 'poke_api_user')
            LOOP
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON public.player_decks, public.player_deck_cards TO %I',
                    rol_aplicacion
                );
            END LOOP;
        END;
        $$;
    """)


def downgrade() -> None:
    """Revierte las tablas en orden inverso."""
    op.drop_index("ix_player_deck_cards_deck_id", table_name="player_deck_cards")
    op.drop_table("player_deck_cards")
    op.drop_index("ix_player_decks_user_id", table_name="player_decks")
    op.drop_table("player_decks")
