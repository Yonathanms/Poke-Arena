"""Normalize card persistence without discarding ambiguous legacy catalog rows.

Revision ID: 002_content_card_persistence
Revises: 001_initial_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_content_card_persistence"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CARD_TYPES = ("FUE", "AGU", "PLA", "ELE", "PSI", "LUC")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "catalog_cards" not in tables:
        raise RuntimeError("No existe catalog_cards; no se puede migrar el catálogo anterior.")
    if "catalog_cards_legacy_002" in tables:
        raise RuntimeError("Ya existe catalog_cards_legacy_002; se aborta para preservar datos.")

    # El modelo anterior no tiene ability_code ni metadatos/hash de archivo. Preservamos
    # las filas completas y las señalamos para conciliación en vez de inventar relaciones.
    op.rename_table("catalog_cards", "catalog_cards_legacy_002")
    for index_name in (
        "ix_catalog_cards_code",
        "ix_catalog_cards_card_type",
        "ix_catalog_cards_rarity",
    ):
        legacy_indexes = {
            index["name"]
            for index in sa.inspect(bind).get_indexes("catalog_cards_legacy_002")
        }
        if index_name in legacy_indexes:
            op.drop_index(index_name, table_name="catalog_cards_legacy_002")

    op.create_table(
        "catalog_abilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(7), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ability_type", sa.String(30), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("has_effect", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("evolution_target_card_id", sa.String(36), nullable=True),
        sa.CheckConstraint("code ~ '^HAB-[0-9]{3}$'", name="ck_catalog_abilities_code"),
        sa.CheckConstraint(
            "(code = 'HAB-000' AND ability_type = 'HAB-000' AND has_effect = false) "
            "OR code <> 'HAB-000'",
            name="ck_catalog_abilities_reserved_none",
        ),
    )
    op.create_table(
        "catalog_card_images",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_storage_key", sa.String(512), nullable=False),
        sa.Column("original_sha256", sa.String(64), nullable=False),
        sa.Column("image_format", sa.String(10), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("thumbnail_storage_key", sa.String(512), nullable=True),
        sa.Column("thumbnail_format", sa.String(10), nullable=True),
        sa.Column("thumbnail_byte_size", sa.Integer(), nullable=True),
        sa.Column("thumbnail_width", sa.Integer(), nullable=True),
        sa.Column("thumbnail_height", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sanitized_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('PENDING', 'PROCESSING', 'RETRY_PENDING', 'READY', 'FAILED')",
            name="ck_catalog_card_images_state",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_catalog_card_images_attempts"),
        sa.CheckConstraint("generation >= 0", name="ck_catalog_card_images_generation"),
        sa.CheckConstraint(
            "original_sha256 ~ '^[0-9a-fA-F]{64}$'", name="ck_catalog_card_images_sha256"
        ),
        sa.CheckConstraint(
            "image_format IN ('PNG', 'JPEG', 'WEBP')", name="ck_catalog_card_images_format"
        ),
        sa.CheckConstraint(
            "thumbnail_format IS NULL OR thumbnail_format = 'WEBP'",
            name="ck_catalog_card_images_thumbnail_format",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_catalog_card_images_byte_size"),
        sa.CheckConstraint("byte_size <= 5000000", name="ck_catalog_card_images_byte_size_limit"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_catalog_card_images_dimensions"),
        sa.CheckConstraint(
            "width >= 600 AND height >= 840 AND width * 7 = height * 5",
            name="ck_catalog_card_images_aspect",
        ),
        sa.CheckConstraint(
            "state <> 'READY' OR (thumbnail_storage_key IS NOT NULL "
            "AND thumbnail_format IS NOT NULL AND thumbnail_byte_size > 0 "
            "AND thumbnail_width = 200 AND thumbnail_height = 280)",
            name="ck_catalog_card_images_ready_thumbnail",
        ),
    )
    op.create_index(
        "ix_catalog_card_images_work",
        "catalog_card_images",
        ["state", "next_attempt_at", "lease_expires_at"],
    )
    op.create_table(
        "catalog_card_code_counters",
        sa.Column("card_type", sa.String(3), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("last_value BETWEEN 0 AND 999", name="ck_card_code_counter_range"),
        sa.CheckConstraint(
            "card_type IN ('FUE', 'AGU', 'PLA', 'ELE', 'PSI', 'LUC')",
            name="ck_card_code_counter_type",
        ),
    )
    op.create_table(
        "catalog_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cost", sa.SmallInteger(), nullable=False),
        sa.Column("power", sa.SmallInteger(), nullable=False),
        sa.Column("card_type", sa.String(3), nullable=False),
        sa.Column("rarity", sa.String(20), nullable=False),
        sa.Column("ability_id", sa.String(36), nullable=False),
        sa.Column("image_id", sa.String(36), nullable=False, unique=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cost BETWEEN 0 AND 10", name="ck_catalog_cards_cost"),
        sa.CheckConstraint("power BETWEEN -20 AND 20", name="ck_catalog_cards_power"),
        sa.CheckConstraint("length(btrim(name)) BETWEEN 1 AND 100", name="ck_catalog_cards_name"),
        sa.CheckConstraint(
            "card_type IN ('FUE', 'AGU', 'PLA', 'ELE', 'PSI', 'LUC')",
            name="ck_catalog_cards_type",
        ),
        sa.CheckConstraint(
            "rarity IN ('COMUN', 'POCO_COMUN', 'RARA', 'LEGENDARIA')",
            name="ck_catalog_cards_rarity",
        ),
        sa.CheckConstraint(
            "code = 'PKA-' || card_type || '-' || right(code, 3) "
            "AND code ~ '^PKA-(FUE|AGU|PLA|ELE|PSI|LUC)-[0-9]{3}$' "
            "AND right(code, 3)::INTEGER BETWEEN 1 AND 999",
            name="ck_catalog_cards_code_type",
        ),
        sa.CheckConstraint("version >= 1", name="ck_catalog_cards_version"),
        sa.ForeignKeyConstraint(["ability_id"], ["catalog_abilities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["image_id"], ["catalog_card_images.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_catalog_cards_card_type", "catalog_cards", ["card_type"])
    op.create_index("ix_catalog_cards_rarity", "catalog_cards", ["rarity"])
    op.execute(
        """
        CREATE FUNCTION prevent_catalog_card_code_change() RETURNS trigger AS $$
        BEGIN
            IF NEW.code <> OLD.code THEN
                RAISE EXCEPTION 'catalog card code is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_cards_code_immutable
        BEFORE UPDATE OF code ON catalog_cards
        FOR EACH ROW EXECUTE FUNCTION prevent_catalog_card_code_change()
        """
    )

    # Seed estable de la opción explícita y los seis contadores. Los códigos de legado
    # válidos quedan reservados para que el asignador nunca los vuelva a generar.
    op.execute(
        sa.text(
            "INSERT INTO catalog_abilities "
            "(id, code, name, ability_type, description, params, has_effect) "
            "VALUES ('00000000-0000-0000-0000-000000000000', 'HAB-000', "
            "'Sin Habilidad', 'HAB-000', '', "
            "'{}'::jsonb, false)"
        )
    )
    op.create_foreign_key(
        "fk_catalog_abilities_evolution_target",
        "catalog_abilities",
        "catalog_cards",
        ["evolution_target_card_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        sa.text(
            "INSERT INTO catalog_card_code_counters (card_type, last_value) "
            "SELECT t.card_type, COALESCE(MAX(CASE "
            "WHEN l.code ~ ('^PKA-' || t.card_type || '-[0-9]{3}$') "
            "THEN right(l.code, 3)::integer ELSE NULL END), 0) "
            "FROM (VALUES ('FUE'), ('AGU'), ('PLA'), ('ELE'), ('PSI'), ('LUC')) "
            "AS t(card_type) LEFT JOIN catalog_cards_legacy_002 l ON true GROUP BY t.card_type"
        )
    )
    op.create_table(
        "catalog_card_migration_issues",
        sa.Column("legacy_card_id", sa.String(36), primary_key=True),
        sa.Column("legacy_code", sa.String(30), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO catalog_card_migration_issues "
            "(legacy_card_id, legacy_code, reason, detected_at) "
            "SELECT id, code, CASE "
            "WHEN code !~ '^PKA-(FUE|AGU|PLA|ELE|PSI|LUC)-[0-9]{3}$' "
            "THEN 'Código legado no oficial; requiere conciliación manual.' "
            "WHEN card_type NOT IN ('FUE', 'AGU', 'PLA', 'ELE', 'PSI', 'LUC') "
            "THEN 'Tipo legado no oficial; requiere conciliación manual.' "
            "WHEN split_part(code, '-', 2) <> card_type "
            "THEN 'Prefijo del código y tipo legado no coinciden.' "
            "WHEN rarity NOT IN ('COMUN', 'POCO_COMUN', 'RARA', 'LEGENDARIA') "
            "THEN 'Rareza legada no oficial; requiere conciliación manual.' "
            "WHEN ability_spec IS NULL "
            "THEN 'Habilidad sin código y semántica ambigua; no se asignó HAB-000.' "
            "WHEN ability_spec->>'ability_type' <> 'HAB-000' "
            "THEN 'ability_spec libre sin mapeo aprobado a ability_code.' "
            "ELSE 'HAB-000 explícito, pero faltan hash y metadatos verificables de imagen.' "
            "END, now() "
            "FROM catalog_cards_legacy_002"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    active_count = bind.execute(sa.text("SELECT count(*) FROM catalog_cards")).scalar_one()
    image_count = bind.execute(sa.text("SELECT count(*) FROM catalog_card_images")).scalar_one()
    extra_abilities = bind.execute(
        sa.text("SELECT count(*) FROM catalog_abilities WHERE code <> 'HAB-000'")
    ).scalar_one()
    if active_count or image_count or extra_abilities:
        raise RuntimeError(
            "No se revierte: hay cartas, imágenes o habilidades que desaparecerían."
        )

    op.drop_table("catalog_card_migration_issues")
    op.drop_index("ix_catalog_cards_rarity", table_name="catalog_cards")
    op.drop_index("ix_catalog_cards_card_type", table_name="catalog_cards")
    op.execute("DROP TRIGGER trg_catalog_cards_code_immutable ON catalog_cards")
    op.execute("DROP FUNCTION prevent_catalog_card_code_change()")
    op.drop_constraint(
        "fk_catalog_abilities_evolution_target", "catalog_abilities", type_="foreignkey"
    )
    op.drop_table("catalog_cards")
    op.drop_table("catalog_card_code_counters")
    op.drop_index("ix_catalog_card_images_work", table_name="catalog_card_images")
    op.drop_table("catalog_card_images")
    op.drop_table("catalog_abilities")
    op.rename_table("catalog_cards_legacy_002", "catalog_cards")
    op.create_index("ix_catalog_cards_code", "catalog_cards", ["code"], unique=True)
    op.create_index("ix_catalog_cards_card_type", "catalog_cards", ["card_type"])
    op.create_index("ix_catalog_cards_rarity", "catalog_cards", ["rarity"])
