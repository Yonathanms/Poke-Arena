"""Exercise the successor on a disposable copy of 008 with representative data."""

import os
import subprocess
import sys
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from src.shared.config import REPOSITORY_ROOT, MigrationSettings
from tests.alembic_support import snapshot_schema

BASE = "008_flex_card_img_dims"
TARGET = "1b2b_card_image_integrity"
ASPECT = "ck_catalog_card_images_aspect"
THUMBNAIL = "ck_catalog_card_images_ready_thumbnail"


def run_migration(url: str, action: str, revision: str, *, violation: str | None = None) -> None:
    """Run the guarded CLI without reporting URLs or driver parameters."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", action, revision],
        cwd=REPOSITORY_ROOT,
        env=os.environ | {"MIGRATION_DATABASE_URL": url, "DATABASE_URL": "", "MONGO_URL": ""},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if violation is None:
        assert result.returncode == 0, f"Alembic {action} {revision} falló en la copia aislada"
    else:
        assert result.returncode != 0
        assert "CheckViolationError" in result.stderr and violation in result.stderr


async def snapshot(
    conn: AsyncConnection,
) -> tuple[str, dict[str, list[dict[str, Any]]], dict[str, tuple[int, str]]]:
    """Read structure and order-independent fingerprints of all non-version rows."""
    revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
    assert isinstance(revision, str)
    schema = await conn.run_sync(snapshot_schema)
    quote = conn.dialect.identifier_preparer.quote
    data = {}
    for table in schema["tables"]:
        name = table["name"]
        if name == "alembic_version":
            continue
        count, digest = (await conn.execute(text(
            "SELECT count(*), md5(coalesce(string_agg(j, ',' ORDER BY j COLLATE \"C\"), '')) "
            f"FROM (SELECT row_to_json(t)::text AS j FROM public.{quote(name)} t) AS records"
        ))).one()
        data[name] = (count, digest)
    return revision, schema, data


async def test_alignment_is_atomic_and_preserves_rows() -> None:
    """Reject both legacy violations, then verify upgrade, downgrade and re-upgrade.

    The target must be a fresh disposable 008 copy. Only this test's synthetic
    row is updated. Source rows, including codes and counters, are fingerprinted.
    """
    url = os.environ.get("SCHEMA_ALIGNMENT_TEST_URL")
    if not url:
        pytest.skip("Requiere SCHEMA_ALIGNMENT_TEST_URL, copia aislada descartable de 008")
    MigrationSettings(_env_file=None, MIGRATION_DATABASE_URL=url)
    engine = create_async_engine(url, hide_parameters=True, connect_args={"timeout": 5})
    image = {"id": str(uuid4())}
    try:
        async with engine.begin() as conn:
            identity = (await conn.execute(text(
                "SELECT current_database(), rolsuper, rolcreatedb, rolcreaterole, "
                "rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user"
            ))).one()
            assert identity[0].startswith("pokearena_alembic_") and not any(identity[1:])
            assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == BASE
            await conn.execute(text(
                "INSERT INTO catalog_card_images "
                "(id, original_storage_key, original_sha256, image_format, byte_size, width, "
                "height, state, thumbnail_storage_key, thumbnail_format, thumbnail_width, "
                "thumbnail_height, created_at, updated_at) VALUES "
                "(:id, 'synthetic/original', repeat('a', 64), 'PNG', 1, 300, 420, "
                "'READY', 'synthetic/thumbnail', 'WEBP', 200, 280, now(), now())"
            ), image)
        for violated_check, repair in [
            (ASPECT, "width=600, height=840"),
            (THUMBNAIL, "thumbnail_byte_size=1"),
        ]:
            async with engine.connect() as conn:
                before = await snapshot(conn)
            run_migration(url, "upgrade", TARGET, violation=violated_check)
            async with engine.begin() as conn:
                assert await snapshot(conn) == before
                await conn.execute(text(
                    f"UPDATE catalog_card_images SET {repair} WHERE id=:id"
                ), image)
        async with engine.connect() as conn:
            _, schema_before, rows_before = await snapshot(conn)
        run_migration(url, "upgrade", TARGET)
        async with engine.connect() as conn:
            revision, schema_after, rows_after = await snapshot(conn)
        assert revision == TARGET and rows_after == rows_before
        for section in schema_before.keys() - {"constraints"}:
            assert schema_after[section] == schema_before[section]
        old_checks = {(c["table_name"], c["name"]): c for c in schema_before["constraints"]}
        new_checks = {(c["table_name"], c["name"]): c for c in schema_after["constraints"]}
        assert old_checks.keys() == new_checks.keys()
        changed = {key for key in old_checks if old_checks[key] != new_checks[key]}
        assert changed == {("catalog_card_images", ASPECT), ("catalog_card_images", THUMBNAIL)}
        assert all(new_checks[key]["validated"] for key in changed)
        run_migration(url, "downgrade", BASE)
        async with engine.connect() as conn:
            assert await snapshot(conn) == (BASE, schema_before, rows_before)
        run_migration(url, "upgrade", TARGET)
        async with engine.connect() as conn:
            assert await snapshot(conn) == (TARGET, schema_after, rows_before)
    finally:
        await engine.dispose()
