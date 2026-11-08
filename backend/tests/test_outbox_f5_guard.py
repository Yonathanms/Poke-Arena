"""Regresión de la política Outbox para F5 sin conexiones ni escrituras."""

import sys
from types import SimpleNamespace
from typing import Any

import pytest
from pymongo import AsyncMongoClient
from sqlalchemy.engine import make_url

from src.database import outbox_worker
from src.database.mongodb import connection
from src.modules.catalogo import catalogo_module as catalogo
from src.shared import config

_PG = "postgresql+asyncpg://app@127.0.0.1:15433/pokearena_alembic_frontend_dev"
_MONGO = "mongodb://proyeccion:prueba@127.0.0.1:27029/pokearena_catalog_frontend_dev"
_BASE = "pokearena_catalog_frontend_dev"


def _ajustes(**cambios: Any) -> config.Settings:
    opciones: dict[str, Any] = {
        "ENVIRONMENT": "development",
        "DATABASE_URL": _PG,
        "MONGO_URL": _MONGO,
        "MONGO_DB": _BASE,
    }
    return config.Settings(_env_file=None, **(opciones | cambios))


@pytest.mark.parametrize("opciones", ["", "?authSource=admin&directConnection=true"])
def test_acepta_f5_exacto(opciones: str) -> None:
    """Acepta ambos destinos exactos con opciones que no cambian el servidor."""
    outbox_worker.verificar_configuracion(_ajustes(MONGO_URL=_MONGO + opciones))


@pytest.mark.parametrize("base", ["pokearena_gridfs_test_demo", "pokearena_outbox_demo"])
async def test_preserva_1f(base: str) -> None:
    """Mantiene los prefijos y clientes 1F sin requerir puerto ni modo directo."""
    url = "mongodb://app:prueba@localhost/" + base
    outbox_worker.verificar_configuracion(
        _ajustes(
            ENVIRONMENT="test",
            DATABASE_URL="postgresql+asyncpg://app@localhost/pokearena_alembic_demo",
            MONGO_URL=url,
            MONGO_DB=base,
        )
    )
    async with AsyncMongoClient[dict[str, Any]](url, connect=False) as cliente:
        catalogo.outbox_mongo.MongoProyeccionCartas(cliente[base]["cards_projection"])


@pytest.mark.parametrize(
    "cambios",
    [
        pytest.param({"MONGO_URL": _MONGO.replace("27029", "27017")}, id="C-mongo-puerto-original"),
        pytest.param(
            {
                "MONGO_URL": "mongodb://app@127.0.0.1:27017/pokearena_catalog",
                "MONGO_DB": "pokearena_catalog",
            },
            id="D-mongo-original",
        ),
        pytest.param({"MONGO_URL": _MONGO.replace("27029", "27028")}, id="E-mongo-1e"),
        pytest.param(
            {"DATABASE_URL": "postgresql+asyncpg://app@127.0.0.1:5432/pokearena"},
            id="F-postgres-original",
        ),
        pytest.param({"DATABASE_URL": _PG.replace("15433", "15432")}, id="G-postgres-1e"),
        pytest.param({"MONGO_URL": _MONGO.replace("127.0.0.1", "remoto.invalid")}, id="H-remoto"),
        pytest.param({"MONGO_DB": _BASE + "_backup"}, id="I-nombre-parecido"),
        pytest.param({"ENVIRONMENT": "production"}, id="J-produccion"),
        pytest.param({"ENVIRONMENT": "test"}, id="J-otro-entorno"),
        pytest.param({"MONGO_URL": _MONGO.replace(":27029", "")}, id="K-mongo-sin-puerto"),
        pytest.param({"MONGO_URL": _MONGO.replace("27029", "abc")}, id="K-mongo-puerto-invalido"),
        pytest.param({"DATABASE_URL": _PG.replace(":15433", "")}, id="K-postgres-sin-puerto"),
        pytest.param(
            {"DATABASE_URL": _PG.replace("15433", "abc")}, id="K-postgres-puerto-invalido"
        ),
        pytest.param(
            {"MONGO_URL": _MONGO.replace(_BASE, "pokearena_catalog")},
            id="L-alias-mongo-original",
        ),
        pytest.param({"MONGO_DB": "pokearena_outbox_demo"}, id="L-base-efectiva-distinta"),
        pytest.param({"DATABASE_URL": _PG + "?host=127.0.0.1:5432"}, id="L-override-postgres"),
        pytest.param({"MONGO_URL": _MONGO + "?replicaSet=otro"}, id="L-topologia-mongo"),
        pytest.param({"MONGO_URL": _MONGO + "?directConnection=false"}, id="L-redescubrimiento"),
        pytest.param(
            {"MONGO_URL": _MONGO.replace("mongodb://", "mongodb+srv://")}, id="L-mongo-srv"
        ),
    ],
)
def test_rechaza_configuraciones_f5(cambios: dict[str, Any]) -> None:
    """Los destinos ambiguos o ajenos fallan con el error sanitizado del CLI."""
    with pytest.raises(ValueError, match="^configuracion_outbox_fuera_de_1f$"):
        outbox_worker.verificar_configuracion(_ajustes(**cambios))


@pytest.mark.parametrize(
    ("host", "puerto", "base", "coleccion", "directa"),
    [
        ("127.0.0.1", 27017, _BASE, "cards_projection", True),
        ("127.0.0.1", 27028, _BASE, "cards_projection", True),
        ("localhost", 27029, _BASE, "cards_projection", True),
        ("127.0.0.1", 27029, _BASE + "_backup", "cards_projection", True),
        ("127.0.0.1", 27029, _BASE, "otra", True),
        ("127.0.0.1", 27029, _BASE, "cards_projection", False),
    ],
)
async def test_adaptador_rechaza_cliente_incorrecto(
    host: str, puerto: int, base: str, coleccion: str, directa: bool
) -> None:
    """Inspecciona la configuración del cliente inyectado sin abrir la red."""
    async with AsyncMongoClient[dict[str, Any]](
        host,
        puerto,
        connect=False,
        directConnection=directa,
    ) as cliente:
        with pytest.raises(ValueError, match="^destino_mongodb_fuera_de_1f$"):
            catalogo.outbox_mongo.MongoProyeccionCartas(cliente[base][coleccion])


async def test_composicion_fija_cliente_f5(monkeypatch: pytest.MonkeyPatch) -> None:
    """La composición oficial fija el destino aunque la URI omita el modo directo."""
    ajustes = _ajustes()
    monkeypatch.setattr(config, "get_settings", lambda: ajustes)
    monkeypatch.setattr(connection, "get_settings", lambda: ajustes)
    monkeypatch.setitem(
        sys.modules, "src.database.postgresql.connection", SimpleNamespace(AsyncSessionLocal=None)
    )
    outbox_worker.verificar_configuracion(ajustes)
    try:
        catalogo.componer_procesador_outbox()
        assert connection.get_mongo_client().options.direct_connection is True
    finally:
        await connection.close_mongo_connection()


async def test_worker_rechaza_motor_sql_ya_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rechaza el motor efectivo si se construyó con otra URL antes de arrancar."""
    monkeypatch.setattr(outbox_worker, "get_settings", _ajustes)
    motor = SimpleNamespace(url=make_url(_PG.replace("15433", "5432")))
    monkeypatch.setitem(
        sys.modules, "src.database.postgresql.connection", SimpleNamespace(engine=motor)
    )
    with pytest.raises(ValueError, match="^configuracion_outbox_fuera_de_1f$"):
        await outbox_worker.run_outbox_worker(una_vez=True)


async def test_adaptador_rechaza_alias_de_base_original() -> None:
    """Seleccionar la colección F5 no autoriza una URI con otra base por defecto."""
    url = _MONGO.replace(_BASE, "pokearena_catalog")
    async with AsyncMongoClient[dict[str, Any]](
        url, connect=False, directConnection=True
    ) as cliente:
        with pytest.raises(ValueError, match="^destino_mongodb_fuera_de_1f$"):
            catalogo.outbox_mongo.MongoProyeccionCartas(cliente[_BASE]["cards_projection"])
