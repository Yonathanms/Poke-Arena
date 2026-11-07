"""Integridad histórica y reconstrucción opt-in sobre dos bases vacías aisladas."""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from typing import Any

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.shared.config import REPOSITORY_ROOT, MigrationSettings
from tests.alembic_support import snapshot_schema

BACKEND = REPOSITORY_ROOT / "backend"
MANIFEST = json.loads((BACKEND / "alembic/history_manifest.json").read_text())


@pytest.mark.parametrize("entry", MANIFEST["migrations"], ids=lambda entry: entry["revision"])
def test_recovered_files_match_historical_bytes(entry: dict[str, str]) -> None:
    """Detecta cualquier reescritura de una revisión recuperada ya aplicada."""
    data = (BACKEND / "alembic/versions" / entry["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    git_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert git_blob == entry["git_blob"]


def test_chain_has_one_base_one_head_and_no_duplicate_revisions() -> None:
    """Valida orden, unicidad y exclusión de 009 sin conectarse a ningún motor."""
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    revisions = list(reversed(list(script.walk_revisions())))
    expected = [*MANIFEST["migrations"], {
        "revision": "1b2b_card_image_integrity", "down_revision": "008_flex_card_img_dims",
    }]
    assert len({r.revision for r in revisions}) == len(revisions) == len(expected)
    assert [r.revision for r in revisions] == [e["revision"] for e in expected]
    assert [r.down_revision for r in revisions] == [e["down_revision"] for e in expected]
    assert script.get_heads() == ["1b2b_card_image_integrity"]
    assert script.get_bases() == ["001_initial_schema"]
    assert not list((BACKEND / "alembic/versions").glob("009*.py"))


def test_migration_settings_do_not_require_mongo_or_application_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Carga mantenimiento con credencial ficticia independiente de la aplicación."""
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("MONGO_URL", "")
    settings = MigrationSettings(
        _env_file=None,
        MIGRATION_DATABASE_URL=(
            "postgresql+asyncpg://migration:fake@localhost/pokearena_alembic_test"
        ),
    )
    assert settings.MIGRATION_DATABASE_URL.startswith("postgresql+asyncpg://")
    assert "fake" not in repr(settings) + settings.model_dump_json()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://poke_api_user:fake@localhost/pokearena_alembic_test",
        "postgresql+asyncpg://migration:fake@localhost/pokearena_db",
        "postgresql+asyncpg://migration:fake@localhost/poke_arena",
        "",
    ],
)
def test_migration_configuration_rejects_unsafe_targets(url: str) -> None:
    """Bloquea antes de conectar las credenciales de API y bases fuera de la fase."""
    with pytest.raises(ValidationError):
        MigrationSettings(_env_file=None, MIGRATION_DATABASE_URL=url)


def test_migrations_never_fall_back_to_application_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """La configuración explícita de mantenimiento es obligatoria."""
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://api:fake@localhost/pokearena_db")
    with pytest.raises(ValidationError):
        MigrationSettings(_env_file=None)


async def inspect_target(url: str, expect_empty: bool) -> dict[str, list[dict[str, Any]]]:
    """Inspecciona únicamente un destino de prueba validado; nunca borra tablas."""
    MigrationSettings(_env_file=None, MIGRATION_DATABASE_URL=url)
    engine = create_async_engine(url, hide_parameters=True, connect_args={"timeout": 5})
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET TRANSACTION READ ONLY"))
            snapshot = await conn.run_sync(snapshot_schema)
            if expect_empty:
                assert snapshot["tables"] == [], "La prueba requiere una base vacía nueva"
            else:
                assert await conn.scalar(
                    text("SELECT version_num FROM alembic_version")
                ) == "008_flex_card_img_dims"
                assert await conn.scalar(
                    text("SELECT count(*) FROM catalog_abilities WHERE code='HAB-000'")
                ) == 1
                assert await conn.scalar(
                    text("SELECT count(*) FROM catalog_card_code_counters WHERE last_value=0")
                ) == 6
            return snapshot
    finally:
        await engine.dispose()


def test_rebuild_twice_in_independent_empty_databases() -> None:
    """Aplica originales dos veces desde cwd distintos y compara estructura completa.

    Opt-in mediante ALEMBIC_TEST_URL_A/B, creadas vacías en instancia aislada por
    el operador. Se rechazan destinos no permitidos y bases no vacías antes de DDL.
    No crea/elimina bases, no ejecuta downgrade ni utiliza stamp. Las credenciales
    se transmiten por entorno y se omiten de los mensajes de fallo.
    """
    urls = [os.environ.get("ALEMBIC_TEST_URL_A"), os.environ.get("ALEMBIC_TEST_URL_B")]
    if not all(urls):
        pytest.skip("Requiere dos bases aisladas vacías: ALEMBIC_TEST_URL_A/B")
    assert urls[0] != urls[1], "Las reconstrucciones deben usar destinos independientes"
    snapshots = []
    for url, cwd, ini in zip(
        urls, [REPOSITORY_ROOT, BACKEND], ["backend/alembic.ini", "alembic.ini"], strict=True
    ):
        assert url is not None
        asyncio.run(inspect_target(url, expect_empty=True))
        env = os.environ.copy()
        env.update(MIGRATION_DATABASE_URL=url, DATABASE_URL="", MONGO_URL="")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", ini, "upgrade", "008_flex_card_img_dims"],
            cwd=cwd, env=env, capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, "Reconstrucción falló; revisar diagnóstico privado"
        snapshots.append(asyncio.run(inspect_target(url, expect_empty=False)))
    assert snapshots[0] == snapshots[1]
    assert len(snapshots[0]["tables"]) == 12
    assert len(snapshots[0]["columns"]) == 103
    assert len(snapshots[0]["constraints"]) == 50
    assert len(snapshots[0]["indexes"]) == 27
    assert len(snapshots[0]["triggers"]) == 1
    foreign_keys = [c for c in snapshots[0]["constraints"] if c["type"] == "f"]
    assert len(foreign_keys) == 4
    primary_keys = {
        c["table_name"]: c["definition"]
        for c in snapshots[0]["constraints"]
        if c["type"] == "p"
    }
    assert len(primary_keys) == 12
    assert primary_keys["catalog_cards"] == "PRIMARY KEY (id)"
    assert primary_keys["catalog_abilities"] == "PRIMARY KEY (id)"
    assert primary_keys["shared_idempotency_records"] == "PRIMARY KEY (id)"
    assert primary_keys["catalog_card_code_counters"] == "PRIMARY KEY (card_type)"
    columns = {(c["table_name"], c["name"]): c for c in snapshots[0]["columns"]}
    assert columns["catalog_cards", "id"]["type"] == "character varying(36)"
    # asyncpg representa el char interno vacío de PostgreSQL como NUL.
    assert columns["catalog_cards", "id"]["identity"].strip("\x00") == ""
    assert not columns["catalog_cards", "image_id"]["not_null"]
    checks = {
        c["name"]: c["definition"]
        for c in snapshots[0]["constraints"]
        if c["type"] == "c"
    }
    assert {
        "ck_catalog_cards_cost", "ck_catalog_cards_power", "ck_catalog_cards_code_type",
        "ck_catalog_cards_type", "ck_catalog_cards_rarity", "ck_card_code_counter_range",
    } <= checks.keys()
    assert "width >= 300" in checks["ck_catalog_card_images_aspect"]
    assert ("catalog_locations", "description") not in columns
