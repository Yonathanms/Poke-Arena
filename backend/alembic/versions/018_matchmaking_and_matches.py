"""Crea tablas de matchmaking y partidas (match_searches, matches, match_players).

Revision ID: 018_matchmaking_and_matches
Revises: 017_drop_outbox_tables
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "018_matchmaking_and_matches"
down_revision: str | None = "017_drop_outbox_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea matches, match_searches y match_players con restricciones ACID e índices."""
    op.create_table(
        "matches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("context", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_bot_match", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("bet_cubes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("turn_number", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("turn_duration_seconds", sa.SmallInteger(), nullable=False, server_default="30"),
        sa.Column("turn_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("turn_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locations_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("deck_orders_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.CheckConstraint("context IN ('RANKED', 'TOURNAMENT')", name="ck_matches_context"),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'FINISHED', 'ABORTED')",
            name="ck_matches_status",
        ),
        sa.CheckConstraint("bet_cubes >= 0", name="ck_matches_bet_cubes_non_negative"),
        sa.CheckConstraint("turn_number >= 1", name="ck_matches_turn_number_positive"),
        sa.CheckConstraint(
            "turn_duration_seconds > 0",
            name="ck_matches_turn_duration_positive",
        ),
        sa.CheckConstraint("state_version >= 1", name="ck_matches_state_version_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_matches"),
    )

    op.create_table(
        "match_searches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("deck_id", sa.String(length=36), nullable=True),
        sa.Column("context", sa.String(length=20), nullable=False),
        sa.Column("elo_snapshot", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("match_id", sa.String(length=36), nullable=True),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
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
        sa.CheckConstraint(
            "context IN ('RANKED', 'TOURNAMENT')",
            name="ck_match_searches_context",
        ),
        sa.CheckConstraint(
            "status IN ('SEARCHING', 'MATCHED', 'CANCELLED', 'EXPIRED')",
            name="ck_match_searches_status",
        ),
        sa.CheckConstraint(
            "status <> 'SEARCHING' OR deck_id IS NOT NULL",
            name="ck_match_searches_active_deck_required",
        ),
        sa.CheckConstraint("state_version >= 1", name="ck_match_searches_state_version_positive"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_match_searches_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deck_id"],
            ["player_decks.id"],
            name="fk_match_searches_deck_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_searches_match_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_searches"),
    )
    op.create_index(
        "uq_match_searches_one_active_per_user",
        "match_searches",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'SEARCHING'"),
    )
    op.create_index(
        "ix_match_searches_queue",
        "match_searches",
        ["status", "context", "last_seen_at", "elo_snapshot"],
    )
    op.create_index(
        "ix_match_searches_deck_active",
        "match_searches",
        ["deck_id"],
        postgresql_where=sa.text("status = 'SEARCHING'"),
    )

    op.create_table(
        "match_players",
        sa.Column("match_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("seat", sa.SmallInteger(), nullable=False),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deck_id", sa.String(length=36), nullable=True),
        sa.Column("deck_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("elo_at_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.CheckConstraint("seat IN (1, 2)", name="ck_match_players_seat"),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'FINISHED', 'ABORTED')",
            name="ck_match_players_status",
        ),
        sa.CheckConstraint(
            "(is_bot = true AND user_id IS NULL) OR (is_bot = false AND user_id IS NOT NULL)",
            name="ck_match_players_bot_user_consistency",
        ),
        sa.CheckConstraint(
            "is_bot = true OR status <> 'IN_PROGRESS' OR deck_id IS NOT NULL",
            name="ck_match_players_active_deck_required",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_players_match_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_match_players_user_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deck_id"],
            ["player_decks.id"],
            name="fk_match_players_deck_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("match_id", "seat", name="pk_match_players"),
    )
    op.create_index(
        "uq_match_players_one_active_per_user",
        "match_players",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL AND status = 'IN_PROGRESS'"),
    )
    op.create_index(
        "ix_match_players_deck_active",
        "match_players",
        ["deck_id"],
        postgresql_where=sa.text("deck_id IS NOT NULL AND status = 'IN_PROGRESS'"),
    )

    op.execute("""
        DO $$
        DECLARE rol_aplicacion name;
        BEGIN
            FOR rol_aplicacion IN
                SELECT rolname FROM pg_roles WHERE rolname IN ('orm_media_test', 'poke_api_user')
            LOOP
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON '
                    'public.match_searches, public.matches, public.match_players TO %I',
                    rol_aplicacion
                );
            END LOOP;
        END;
        $$;
    """)


def downgrade() -> None:
    """Revierte match_players, match_searches y matches en orden inverso."""
    op.drop_index("ix_match_players_deck_active", table_name="match_players")
    op.drop_index("uq_match_players_one_active_per_user", table_name="match_players")
    op.drop_table("match_players")

    op.drop_index("ix_match_searches_deck_active", table_name="match_searches")
    op.drop_index("ix_match_searches_queue", table_name="match_searches")
    op.drop_index("uq_match_searches_one_active_per_user", table_name="match_searches")
    op.drop_table("match_searches")

    op.drop_table("matches")
