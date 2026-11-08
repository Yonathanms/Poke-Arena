"""Contratos ORM y repositorio sobre una base aislada en la revisión objetivo."""

import ast
import asyncio
import os
import re
import subprocess
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import (
    CheckConstraint,
    DefaultClause,
    Table,
    UniqueConstraint,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import DBAPIError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import configure_mappers, selectinload

from src.database.postgresql.base import Base
from src.modules.catalogo import catalogo_module as catalogo
from src.shared.config import REPOSITORY_ROOT, MigrationSettings, get_settings
from src.shared.idempotencia.models import IdempotencyRecordORM
from src.shared.outbox import OutboxEventORM

SessionFactory = async_sessionmaker[AsyncSession]
TransactionContext = Callable[[SessionFactory], AbstractAsyncContextManager[AsyncSession]]

MODELOS = {m.__tablename__: m for m in catalogo.modelos_persistencia()}
CartaORM = cast(type[Any], MODELOS["catalog_cards"])
HabilidadORM = cast(type[Any], MODELOS["catalog_abilities"])
ImagenORM = cast(type[Any], MODELOS["catalog_card_images"])
ContadorORM = cast(type[Any], MODELOS["catalog_card_code_counters"])
Carta = catalogo.dominio_cartas.Carta
ErrorPersistencia = catalogo.puertos_cartas.ErrorPersistencia
TIPO = catalogo.puertos_cartas.TipoErrorPersistencia
SIN_HABILIDAD = "00000000-0000-0000-0000-000000000000"
BACKEND = REPOSITORY_ROOT / "backend"


def nueva_carta(**cambios: Any) -> Any:
    """Fixture pura: no asigna consecutivos ni toca bases originales."""
    datos = dict(
        id=str(uuid4()), code="PKA-FUE-001", name="Carta aislada", cost=0, power=-20,
        card_type="FUE", rarity="COMUN", ability_id=SIN_HABILIDAD,
        created_at=datetime.now(UTC),
    )
    return Carta(**(datos | cambios))


def test_unique_registry_and_composition() -> None:
    """Carga repetida conserva identidades, seis tablas y un único propietario."""
    configure_mappers()
    assert len(Base.registry.mappers) == len(Base.metadata.tables) == len(MODELOS) == 6
    assert catalogo.modelos_persistencia() == catalogo.modelos_persistencia()
    assert MODELOS["shared_idempotency_records"] is IdempotencyRecordORM
    assert MODELOS["shared_outbox"] is OutboxEventORM
    for model in MODELOS.values():
        assert model.metadata is Base.metadata
        assert cast(Table, model.__table__).primary_key.name
    assert inspect(CartaORM).relationships.habilidad.local_columns == {
        CartaORM.ability_id.property.columns[0]
    }
    assert not inspect(ImagenORM).relationships.carta.uselist
    assert inspect(CartaORM).relationships.imagen.lazy == "raise"
    assert "delete" not in inspect(HabilidadORM).relationships.cartas.cascade


def test_composition_imports_without_settings_or_connections() -> None:
    """Un proceso limpio registra mapeos sin cargar runtime, Mongo o worker."""
    code = """
import sys
from src.modules.catalogo import catalogo_module as c
from sqlalchemy.orm import configure_mappers
configure_mappers()
assert len(c.modelos_persistencia()) == 6
assert 'src.database.postgresql.connection' not in sys.modules
assert 'src.database.mongodb.connection' not in sys.modules
assert 'src.database.outbox_worker' not in sys.modules
assert 'src.shared.config' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND,
        env=os.environ | {"DATABASE_URL": "", "MONGO_URL": ""},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_hexagonal_dependencies_and_single_dynamic_boundary() -> None:
    """Dominio/puertos puros e importlib solo en composición; no hacks de rutas."""
    folder = BACKEND / "src/modules/catalogo/gestion-cartas"
    for path in folder.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                assert not any("importlib" in name for name in names)
                if path.parent.name in {"domain", "ports"}:
                    assert not any(
                        any(word in name for word in (
                            "sqlalchemy", "fastapi", "database", "adapters", "pymongo",
                        ))
                        for name in names
                    )
        assert "sys.path" not in path.read_text(encoding="utf-8-sig")


def test_checks_match_immutable_historical_migrations() -> None:
    """Compara los CHECK con la cadena histórica y su sucesora de imágenes."""
    expected = {}
    for path in sorted((BACKEND / "alembic/versions").glob("*.py")):
        upgrade = next(
            node for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
        )
        for node in ast.walk(upgrade):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "CheckConstraint":
                name = ast.literal_eval(next(k.value for k in node.keywords if k.arg == "name"))
                expected[name] = ast.literal_eval(node.args[0])
            elif node.func.attr == "create_check_constraint":
                expected[ast.literal_eval(node.args[0])] = ast.literal_eval(node.args[2])
    for model in MODELOS.values():
        for constraint in cast(Table, model.__table__).constraints:
            if isinstance(constraint, CheckConstraint):
                assert constraint.name is not None
                assert " ".join(str(constraint.sqltext).split()) == " ".join(
                    expected[constraint.name].split()
                )


@pytest_asyncio.fixture
async def factory(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[SessionFactory]:
    """Autoriza DML únicamente con URL opt-in aislada, sin limpiar ni crear tablas.

    Cada prueba usa transacciones revertidas salvo la prueba explícita de commit,
    que conserva su fila en la base descartable. Nunca usa DATABASE_URL como fallback.
    """
    url = os.environ.get("ORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requiere ORM_TEST_DATABASE_URL aislada en 1b2b_card_image_integrity")
    MigrationSettings(_env_file=None, MIGRATION_DATABASE_URL=url)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    from src.database.postgresql import connection
    engine = connection.engine
    assert connection.Base is Base
    assert engine.url == make_url(url), "La fábrica oficial debe apuntar al destino aislado"
    try:
        async with engine.connect() as conn:
            database = await conn.scalar(text("SELECT current_database()"))
            assert database.startswith("pokearena_alembic_")
            revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "1b2b_card_image_integrity"
            assert not await conn.scalar(text(
                "SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
            ))
        yield connection.AsyncSessionLocal
    finally:
        await engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def transaction_context(factory: SessionFactory) -> TransactionContext:
    """Carga el límite transaccional oficial solo después de configurar aislamiento."""
    from src.database.postgresql.connection import transactional_session
    return transactional_session


def constraint_name(error: DBAPIError) -> str | None:
    """Lee el nombre técnico del constraint sin registrar SQL ni parámetros."""
    value = getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)
    return value if isinstance(value, str) else None


def _default(value: object) -> str | None:
    """Normaliza solo casts de los defaults escalares conocidos en estas seis tablas."""
    if value is None:
        return None
    literal = str(value).strip()
    integer = re.fullmatch(r"'(-?\d+)'::(?:bigint|integer)", literal)
    if integer:
        return integer[1]
    return re.sub(r"::(?:character varying|text)$", "", literal)


def test_text_default_comparison_preserves_case() -> None:
    """Los casts equivalentes se normalizan, pero el contenido SQL no se altera."""
    assert _default("'PENDING'::character varying") == _default("'PENDING'")
    assert _default("'PENDING'::character varying") != _default("'pending'")
    assert _default("'PENDING '::character varying") != _default("'PENDING'")
    assert _default("'1'::bigint") == _default("1")
    assert _default(None) is None


def _compare_metadata(conn: Connection) -> None:
    """Contrasta todas las columnas, claves y los índices explícitos contra PostgreSQL."""
    inspector = inspect(conn)
    dialect = conn.dialect
    for name, model in MODELOS.items():
        table = cast(Table, model.__table__)
        actual = inspector.get_columns(name)
        assert [c["name"] for c in actual] == list(table.columns.keys())
        for reflected, column in zip(actual, table.columns, strict=True):
            assert reflected["type"].compile(dialect=dialect) == column.type.compile(
                dialect=dialect
            )
            assert reflected["nullable"] == column.nullable
            default = column.server_default
            assert default is None or isinstance(default, DefaultClause)
            assert _default(reflected["default"]) == _default(default.arg if default else None)
            assert not reflected.get("identity") and not reflected.get("computed")
            assert column.default is None
        pk = inspector.get_pk_constraint(name)
        assert pk["name"] == table.primary_key.name
        assert pk["constrained_columns"] == [c.name for c in table.primary_key]
        uniques = {u["name"]: u["column_names"] for u in inspector.get_unique_constraints(name)}
        assert uniques == {
            c.name: list(c.columns.keys()) for c in table.constraints
            if isinstance(c, UniqueConstraint)
        }
        foreigns = inspector.get_foreign_keys(name)
        assert {f["name"] for f in foreigns} == {f.name for f in table.foreign_key_constraints}
        for reflected_fk in foreigns:
            fk = next(f for f in table.foreign_key_constraints if f.name == reflected_fk["name"])
            assert reflected_fk["constrained_columns"] == list(fk.columns.keys())
            assert reflected_fk["referred_table"] == fk.referred_table.name
            assert reflected_fk["referred_columns"] == [e.column.name for e in fk.elements]
            assert reflected_fk["options"].get("ondelete") == fk.ondelete == "RESTRICT"
            assert not reflected_fk["options"].get("deferrable") and not fk.deferrable
        assert {c["name"] for c in inspector.get_check_constraints(name)} == {
            c.name for c in table.constraints if isinstance(c, CheckConstraint)
        }
        indexes = {
            i["name"]: (i["column_names"], i["unique"])
            for i in inspector.get_indexes(name) if not i.get("duplicates_constraint")
        }
        assert indexes == {i.name: (list(i.columns.keys()), i.unique) for i in table.indexes}


async def test_metadata_matches_real_postgresql(factory: SessionFactory) -> None:
    """Metadata parcial exacta en las seis tablas; no ejecuta create_all/autogenerate."""
    async with factory() as session:
        conn = await session.connection()
        await conn.run_sync(_compare_metadata)


async def test_repository_reads_writes_and_relationships(factory: SessionFactory) -> None:
    """Prueba FK normal y circular, imagen opcional/uno-a-uno y estados separados."""
    async with factory() as session:
        async with session.begin():
            repo = catalogo.crear_repositorio_cartas(session)
            habilidad = await repo.buscar_habilidad_por_codigo("HAB-000")
            assert habilidad.id == SIN_HABILIDAD and not habilidad.has_effect
            assert await repo.buscar_habilidad_por_codigo("HAB-999") is None
            assert await repo.buscar_por_id(str(uuid4())) is None
            assert await repo.buscar_por_codigo("PKA-FUE-999") is None
            assert await repo.bloquear_contador("FUE") == 0
            assert await repo.bloquear_contador("XXX") is None
            carta = nueva_carta()
            await repo.agregar(carta)
            assert await repo.buscar_por_id(carta.id) == carta
            assert await repo.buscar_por_codigo(carta.code) == carta
            fila = await session.scalar(select(CartaORM).where(CartaORM.id == carta.id))
            assert fila is not None
            with pytest.raises(InvalidRequestError):
                _ = fila.habilidad
            now = datetime.now(UTC)
            imagen = ImagenORM(
                id=str(uuid4()), original_storage_key="isolated/original", original_sha256="a"*64,
                image_format="PNG", byte_size=1, width=600, height=840,
                created_at=now, updated_at=now,
            )
            session.add(imagen)
            await session.flush()
            assert imagen.state == "PENDING" and imagen.attempts == imagen.generation == 0
            fila.image_id = imagen.id
            await session.flush()
            evolucion = HabilidadORM(
                id=str(uuid4()), code="HAB-001", name="Evolución", ability_type="EVOLUTION",
                params={}, evolution_target_card_id=carta.id,
            )
            session.add(evolucion)
            await session.flush()
            session.expire_all()
            fila = await session.scalar(select(CartaORM).where(CartaORM.id == carta.id).options(
                selectinload(CartaORM.habilidad), selectinload(CartaORM.imagen),
            ))
            assert fila is not None
            assert fila.habilidad.code == "HAB-000" and fila.imagen.id == imagen.id
            evolucion = await session.scalar(
                select(HabilidadORM).where(HabilidadORM.code == "HAB-001")
                .options(selectinload(HabilidadORM.destino_evolucion))
            )
            assert evolucion is not None
            assert evolucion.destino_evolucion.id == carta.id
            await session.rollback()


@pytest.mark.parametrize("cambios,restriccion,tipo", [
    ({"cost": -1}, "ck_catalog_cards_cost", TIPO.RESTRICCION),
    ({"cost": 11}, "ck_catalog_cards_cost", TIPO.RESTRICCION),
    ({"power": -21}, "ck_catalog_cards_power", TIPO.RESTRICCION),
    ({"power": 21}, "ck_catalog_cards_power", TIPO.RESTRICCION),
    ({"code": "PKA-FUE-000"}, "ck_catalog_cards_code_type", TIPO.RESTRICCION),
    ({"code": "PKA-FUE-1000"}, "ck_catalog_cards_code_type", TIPO.RESTRICCION),
    ({"code": "PKA-AGU-001"}, "ck_catalog_cards_code_type", TIPO.RESTRICCION),
    ({"card_type": "XXX"}, "ck_catalog_cards_type", TIPO.RESTRICCION),
    ({"rarity": "INVALIDA"}, "ck_catalog_cards_rarity", TIPO.RESTRICCION),
    ({"name": "   "}, "ck_catalog_cards_name", TIPO.RESTRICCION),
    ({"version": 0}, "ck_catalog_cards_version", TIPO.RESTRICCION),
    ({"ability_id": "missing"}, "catalog_cards_ability_id_fkey", TIPO.REFERENCIA),
    ({"ability_id": None}, None, TIPO.RESTRICCION),
    ({"image_id": "missing"}, "catalog_cards_image_id_fkey", TIPO.REFERENCIA),
])
async def test_repository_constraint_errors(
    factory: SessionFactory, cambios: dict[str, Any], restriccion: str | None, tipo: str,
) -> None:
    """Restricciones reales y errores sanitizados; rollback queda en el llamador."""
    async with factory() as session:
        with pytest.raises(ErrorPersistencia) as exc:
            async with session.begin():
                await catalogo.crear_repositorio_cartas(session).agregar(nueva_carta(**cambios))
        assert exc.value.tipo == tipo
        if restriccion and cambios.get("card_type") != "XXX":
            assert exc.value.restriccion == restriccion
        assert "INSERT" not in str(exc.value) and "Carta aislada" not in str(exc.value)
        assert not session.in_transaction()
        async with session.begin():
            repo = catalogo.crear_repositorio_cartas(session)
            assert await repo.buscar_por_codigo("PKA-FUE-001") is None


@pytest.mark.parametrize("cost,power,code", [(0, -20, "PKA-FUE-001"), (10, 20, "PKA-FUE-999")])
async def test_valid_card_boundaries(
    factory: SessionFactory, cost: int, power: int, code: str,
) -> None:
    """SQL conserva los límites inclusivos sin consumir contadores por repositorio."""
    async with factory() as session:
        async with session.begin():
            repo = catalogo.crear_repositorio_cartas(session)
            await repo.agregar(nueva_carta(cost=cost, power=power, code=code))
            assert await repo.bloquear_contador("FUE") == 0
            await session.rollback()


async def test_unique_code_and_trigger_immutable(factory: SessionFactory) -> None:
    """Unicidad y trigger histórico siguen vigentes sin recrearlos desde ORM."""
    async with factory() as session:
        with pytest.raises(ErrorPersistencia) as exc:
            async with session.begin():
                repo = catalogo.crear_repositorio_cartas(session)
                await repo.agregar(nueva_carta())
                await repo.agregar(nueva_carta())
        assert exc.value.tipo == TIPO.DUPLICADO
        assert exc.value.restriccion == "catalog_cards_code_key"
        with pytest.raises(DBAPIError):
            async with session.begin():
                carta = nueva_carta()
                await catalogo.crear_repositorio_cartas(session).agregar(carta)
                await session.execute(
                    update(CartaORM).where(CartaORM.id == carta.id).values(code="PKA-FUE-002")
                )


async def test_transaction_owner_commit_rollback_and_close(
    factory: SessionFactory, transaction_context: TransactionContext,
) -> None:
    """Dos sesiones prueban visibilidad, atomicidad, recuperación y cierre del pool."""
    carta = nueva_carta(code="PKA-ELE-997", card_type="ELE")
    async with transaction_context(factory) as session:
        repo = catalogo.crear_repositorio_cartas(session)
        await repo.agregar(carta)
        async with factory() as reader, reader.begin():
            assert await catalogo.crear_repositorio_cartas(reader).buscar_por_id(carta.id) is None
    assert not session.in_transaction() and not session.identity_map
    async with transaction_context(factory) as reader:
        assert await catalogo.crear_repositorio_cartas(reader).buscar_por_id(carta.id) == carta
    revertida = replace(carta, id=str(uuid4()), code="PKA-ELE-998")
    with pytest.raises(ValueError):
        async with transaction_context(factory) as session:
            await catalogo.crear_repositorio_cartas(session).agregar(revertida)
            await session.execute(
                update(ContadorORM).where(ContadorORM.card_type == "ELE").values(last_value=998)
            )
            raise ValueError("Fallo de coordinación aislado")
    async with transaction_context(factory) as session:
        repo = catalogo.crear_repositorio_cartas(session)
        assert await repo.buscar_por_id(revertida.id) is None
        assert await repo.bloquear_contador("ELE") == 0
    assert factory.kw["bind"].pool.status() == "NullPool"


async def test_explicit_transaction_required(factory: SessionFactory) -> None:
    """Sin límite transaccional del llamador, el adaptador rechaza incluso lecturas."""
    async with factory() as session:
        repo = catalogo.crear_repositorio_cartas(session)
        with pytest.raises(RuntimeError, match="transacción explícita"):
            await repo.buscar_por_id("none")
        assert not session.in_transaction()


@pytest.mark.parametrize("method", [
    "buscar_por_id", "buscar_por_codigo", "buscar_habilidad_por_codigo",
    "agregar", "bloquear_contador",
])
async def test_autobegin_is_rejected(factory: SessionFactory, method: str) -> None:
    """Una consulta previa no sustituye BEGIN explícito en ninguna operación."""
    carta = nueva_carta(code="PKA-FUE-123")
    async with factory() as session:
        await session.execute(text("SELECT 1"))
        transaction = session.sync_session.get_transaction()
        assert transaction is not None and transaction.origin.name == "AUTOBEGIN"
        repo = catalogo.crear_repositorio_cartas(session)
        argument = carta if method == "agregar" else "FUE"
        with pytest.raises(RuntimeError, match="transacción explícita"):
            await getattr(repo, method)(argument)
        # El rechazo no confirma, revierte ni cierra la transacción del llamador.
        assert session.sync_session.get_transaction() is transaction
        await session.rollback()
        async with session.begin():
            assert await repo.buscar_por_id(carta.id) is None


async def test_explicit_root_allows_savepoint(factory: SessionFactory) -> None:
    """Un savepoint no cambia el origen explícito de la transacción raíz."""
    async with factory() as session, session.begin():
        async with session.begin_nested():
            assert await catalogo.crear_repositorio_cartas(session).bloquear_contador("FUE") == 0


async def test_lock_timeout_is_translated(factory: SessionFactory) -> None:
    """Un timeout PostgreSQL real se traduce y el llamador conserva el rollback."""
    async with factory() as first, factory() as second:
        async with first.begin():
            initial = await catalogo.crear_repositorio_cartas(first).bloquear_contador("FUE")
            with pytest.raises(ErrorPersistencia) as exc:
                async with second.begin():
                    await second.execute(text("SET LOCAL lock_timeout = '150ms'"))
                    await asyncio.wait_for(
                        catalogo.crear_repositorio_cartas(second).bloquear_contador("FUE"), 2
                    )
            assert exc.value.tipo == TIPO.OPERACION
            driver_error = exc.value.__context__
            assert isinstance(driver_error, DBAPIError)
            assert getattr(driver_error.orig, "sqlstate", None) == "55P03"
            assert exc.value.__suppress_context__
            assert not second.in_transaction()
            await first.rollback()
        async with second.begin():
            repository = catalogo.crear_repositorio_cartas(second)
            assert await repository.bloquear_contador("FUE") == initial


async def test_counter_lock_is_held_until_transaction_end(
    factory: SessionFactory, transaction_context: TransactionContext,
) -> None:
    """PostgreSQL identifica al bloqueador real; una demora sin SQL no aprueba.

    Tres conexiones independientes observan la espera. Los límites de servidor
    y asyncio evitan esperas indefinidas incluso ante una regresión.
    """
    async with factory() as first, factory() as second, factory() as observer:
        async with first.begin(), second.begin(), observer.begin():
            counters_before = (await first.execute(
                select(ContadorORM.card_type, ContadorORM.last_value)
                .order_by(ContadorORM.card_type)
            )).all()
            first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
            second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
            observer_pid = await observer.scalar(text("SELECT pg_backend_pid()"))
            assert len({first_pid, second_pid, observer_pid}) == 3
            await second.execute(text("SET LOCAL lock_timeout = '4s'"))
            await second.execute(text("SET LOCAL statement_timeout = '5s'"))
            initial = await catalogo.crear_repositorio_cartas(first).bloquear_contador("FUE")
            task = asyncio.create_task(
                catalogo.crear_repositorio_cartas(second).bloquear_contador("FUE")
            )
            try:
                async with asyncio.timeout(2):
                    while True:
                        await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                        blocked = await observer.scalar(text(
                            "SELECT wait_event_type = 'Lock' "
                            "AND :first = ANY(pg_blocking_pids(pid)) "
                            "FROM pg_stat_activity WHERE pid = :second"
                        ), {"first": first_pid, "second": second_pid})
                        if blocked:
                            break
                        assert not task.done(), "No hubo bloqueo SQL entre las dos transacciones"
                        await asyncio.sleep(.01)
                assert not task.done()
                await first.rollback()
                assert await asyncio.wait_for(task, 2) == initial
                await second.rollback()
                counters_after = (await observer.execute(
                    select(ContadorORM.card_type, ContadorORM.last_value)
                    .order_by(ContadorORM.card_type)
                )).all()
                assert counters_after == counters_before
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)


async def test_shared_models_constraints_and_json_null(factory: SessionFactory) -> None:
    """Idempotencia scope/pares SQL NULL y Outbox únicos, sin worker ni política nueva."""
    now = datetime.now(UTC)
    def record(**changes: Any) -> Any:
        return IdempotencyRecordORM(**(dict(
            id=str(uuid4()), actor_id="actor", operation="create", idempotency_key="test",
            request_hash="a"*64, endpoint="/isolated", created_at=now,
            response_status=None, response_body=None,
        ) | changes))
    async with factory() as session:
        async with session.begin():
            session.add(record())
            await session.flush()
            assert await session.scalar(text(
                "SELECT response_body IS NULL FROM shared_idempotency_records"
            ))
            session.add(record(actor_id="other"))
            session.add(record(operation="other"))
            await session.flush()
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    session.add(record())
                    await session.flush()
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    session.add(record(idempotency_key="bad", response_status=201))
                    await session.flush()
            event_values = dict(
                event_type="isolated", payload={}, status="PENDING", created_at=now,
                aggregate_type="card", aggregate_id=str(uuid4()), aggregate_version=1,
                schema_version=1, attempts=0,
            )
            session.add(OutboxEventORM(id=str(uuid4()), **event_values))
            await session.flush()
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    session.add(OutboxEventORM(id=str(uuid4()), **event_values))
                    await session.flush()
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    session.add(OutboxEventORM(**(event_values | {
                        "id": str(uuid4()), "aggregate_version": 2, "attempts": -1,
                    })))
                    await session.flush()
            await session.rollback()


READY_THUMBNAIL = {
    "state": "READY", "thumbnail_storage_key": "isolated/thumbnail", "thumbnail_format": "WEBP",
    "thumbnail_byte_size": 1, "thumbnail_width": 200, "thumbnail_height": 280,
}


@pytest.mark.parametrize("changes,constraint", [
    ({"width": 300, "height": 420}, "ck_catalog_card_images_aspect"),
    ({"width": 601}, "ck_catalog_card_images_aspect"),
    ({"byte_size": 5000001}, "ck_catalog_card_images_byte_size_limit"),
    ({"original_sha256": "invalid"}, "ck_catalog_card_images_sha256"),
    ({"image_format": "GIF"}, "ck_catalog_card_images_format"),
    ({"state": "READY"}, "ck_catalog_card_images_ready_thumbnail"),
    *[
        (READY_THUMBNAIL | {field: None}, "ck_catalog_card_images_ready_thumbnail")
        for field in ("thumbnail_byte_size", "thumbnail_width", "thumbnail_height")
    ],
    (READY_THUMBNAIL | {"thumbnail_width": 201}, "ck_catalog_card_images_ready_thumbnail"),
])
async def test_image_metadata_constraints(
    factory: SessionFactory, changes: dict[str, Any], constraint: str,
) -> None:
    """Rechaza originales antes tolerados y metadatos fuera del contrato."""
    now = datetime.now(UTC)
    values = dict(
        id=str(uuid4()), original_storage_key="isolated/original", original_sha256="a"*64,
        image_format="PNG", byte_size=1, width=600, height=840,
        created_at=now, updated_at=now,
    )
    async with factory() as session:
        with pytest.raises(DBAPIError) as exc:
            async with session.begin():
                session.add(ImagenORM(**(values | changes)))
                await session.flush()
        assert constraint_name(exc.value) == constraint


@pytest.mark.parametrize("width,height", [(600, 840), (1533916890, 2147483646)])
async def test_valid_ready_image_metadata(factory: SessionFactory, width: int, height: int) -> None:
    """Accept a complete READY thumbnail and evaluate ratio without integer overflow."""
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        session.add(ImagenORM(
            id=str(uuid4()), original_storage_key="isolated/original", original_sha256="a" * 64,
            image_format="WEBP", byte_size=5000000, width=width, height=height,
            created_at=now, updated_at=now, **READY_THUMBNAIL,
        ))
        await session.flush()
        await session.rollback()


async def test_counter_capacity_preserves_value_on_overflow(factory: SessionFactory) -> None:
    """The last assignable number is valid and the next one violates the CHECK."""
    async with factory() as session, session.begin():
        counter = update(ContadorORM).where(ContadorORM.card_type == "FUE")
        await session.execute(counter.values(last_value=999))
        repo = catalogo.crear_repositorio_cartas(session)
        with pytest.raises(DBAPIError) as exc:
            async with session.begin_nested():
                await session.execute(counter.values(last_value=1000))
        assert constraint_name(exc.value) == "ck_card_code_counter_range"
        assert await repo.bloquear_contador("FUE") == 999
        await session.rollback()


async def test_unique_image_reference_and_ability_constraints(factory: SessionFactory) -> None:
    """Una imagen no se comparte entre cartas; se conservan seed y FK de evolución."""
    now = datetime.now(UTC)
    async with factory() as session:
        async with session.begin():
            image_id = str(uuid4())
            session.add(ImagenORM(
                id=image_id, original_storage_key="isolated/original",
                original_sha256="a"*64, image_format="PNG", byte_size=1,
                width=600, height=840, created_at=now, updated_at=now,
            ))
            await session.flush()
            repo = catalogo.crear_repositorio_cartas(session)
            await repo.agregar(nueva_carta(image_id=image_id))
            with pytest.raises(ErrorPersistencia) as exc:
                async with session.begin_nested():
                    await repo.agregar(nueva_carta(code="PKA-FUE-002", image_id=image_id))
            assert exc.value.restriccion == "catalog_cards_image_id_key"
            with pytest.raises(DBAPIError) as exc:
                async with session.begin_nested():
                    await session.execute(update(HabilidadORM).where(
                        HabilidadORM.code == "HAB-000"
                    ).values(has_effect=True))
            assert constraint_name(exc.value) == "ck_catalog_abilities_reserved_none"
            with pytest.raises(DBAPIError) as exc:
                async with session.begin_nested():
                    session.add(HabilidadORM(
                        id=str(uuid4()), code="HAB-002", name="Evolución inválida",
                        ability_type="EVOLUTION", params={}, evolution_target_card_id="missing",
                    ))
                    await session.flush()
            assert constraint_name(exc.value) == (
                "fk_catalog_abilities_evolution_target"
            )
            await session.rollback()
