"""Crea las tablas maestras de tipos elementales y rarezas de cartas.

Revision ID: 016_card_types_and_rarities
Revises: 015_player_decks
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016_card_types_and_rarities"
down_revision: str | None = "015_player_decks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea catalog_card_types y catalog_card_rarities, las puebla y añade FKs a catalog_cards."""
    # 1. Tabla de Tipos Elementales
    op.create_table(
        "catalog_card_types",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name="pk_catalog_card_types"),
    )
    op.create_index("ix_catalog_card_types_name", "catalog_card_types", ["name"])

    # 2. Tabla de Rarezas
    op.create_table(
        "catalog_card_rarities",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name="pk_catalog_card_rarities"),
    )
    op.create_index("ix_catalog_card_rarities_name", "catalog_card_rarities", ["name"])

    # 3. Poblar valores por defecto para que las cartas existentes no violen las FKs
    op.execute("""
        INSERT INTO public.catalog_card_types (code, name, description) VALUES
            ('FUE', 'Fuego', 'Energía y ataques ígneos'),
            ('AGU', 'Agua', 'Ataques acuáticos y curación'),
            ('PLA', 'Planta', 'Fuerza natural y absorción'),
            ('ELE', 'Eléctrico', 'Ataques relámpago y parálisis'),
            ('PSI', 'Psíquico', 'Poderes mentales y control'),
            ('LUC', 'Lucha', 'Fuerza física y combate directo')
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description;
    """)

    op.execute("""
        INSERT INTO public.catalog_card_rarities (code, name) VALUES
            ('COMUN', 'Común'),
            ('POCO_COMUN', 'Poco Común'),
            ('RARA', 'Rara'),
            ('LEGENDARIA', 'Legendaria')
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name;
    """)

    # 4. Remover los CHECK constraints quemados en catalog_cards para que la base de datos sea dinámica
    op.drop_constraint("ck_catalog_cards_type", "catalog_cards", type_="check")
    op.drop_constraint("ck_catalog_cards_rarity", "catalog_cards", type_="check")

    # 5. Agregar Foreign Keys con ON UPDATE CASCADE para permitir renombrado futuro
    op.create_foreign_key(
        "fk_catalog_cards_card_type",
        "catalog_cards",
        "catalog_card_types",
        ["card_type"],
        ["code"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )

    op.create_foreign_key(
        "fk_catalog_cards_rarity",
        "catalog_cards",
        "catalog_card_rarities",
        ["rarity"],
        ["code"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )

    # 6. Asignar permisos al rol de aplicación
    op.execute("""
        DO $$
        DECLARE rol_aplicacion name;
        BEGIN
            FOR rol_aplicacion IN
                SELECT rolname FROM pg_roles WHERE rolname IN ('orm_media_test', 'poke_api_user')
            LOOP
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON public.catalog_card_types, public.catalog_card_rarities TO %I',
                    rol_aplicacion
                );
            END LOOP;
        END;
        $$;
    """)


def downgrade() -> None:
    """Revierte las claves foráneas, restituye los checks y elimina las tablas."""
    op.drop_constraint("fk_catalog_cards_rarity", "catalog_cards", type_="foreignkey")
    op.drop_constraint("fk_catalog_cards_card_type", "catalog_cards", type_="foreignkey")

    op.create_check_constraint(
        "ck_catalog_cards_type",
        "catalog_cards",
        "card_type IN ('FUE', 'AGU', 'PLA', 'ELE', 'PSI', 'LUC')",
    )
    op.create_check_constraint(
        "ck_catalog_cards_rarity",
        "catalog_cards",
        "rarity IN ('COMUN', 'POCO_COMUN', 'RARA', 'LEGENDARIA')",
    )

    op.drop_index("ix_catalog_card_rarities_name", table_name="catalog_card_rarities")
    op.drop_table("catalog_card_rarities")
    op.drop_index("ix_catalog_card_types_name", table_name="catalog_card_types")
    op.drop_table("catalog_card_types")

