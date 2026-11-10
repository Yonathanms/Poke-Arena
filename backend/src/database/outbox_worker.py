"""Punto de entrada independiente para el consumidor CardCreated de 1F."""

import argparse
import asyncio
import logging
import signal
from urllib.parse import urlsplit

from pydantic import ValidationError
from pymongo.errors import PyMongoError
from pymongo.uri_parser import parse_uri
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from src.database.mongodb.connection import close_mongo_connection, verificar_mongo_original
from src.database.mongodb.destinos_outbox import MONGO_F5_BASE, MONGO_F5_SERVIDOR, PREFIJOS_MONGO_1F
from src.modules.catalogo.catalogo_module import componer_procesador_outbox
from src.shared.config import Settings, get_settings

logger = logging.getLogger("pokearena.outbox_worker")
_POSTGRES_F5_PUERTOS = {5432, 15433}
_POSTGRES_F5_BASE = "pokearena_alembic_frontend_dev"
_MONGO_F5_PUERTOS = {27017, 27029}


def _verificar_f5(ajustes: Settings) -> None:
    """Verifica el destino de ambos drivers sin conectarse a los motores."""
    sql = make_url(ajustes.DATABASE_URL)
    mongo = parse_uri(ajustes.MONGO_URL, warn=False)
    if (
        ajustes.ENVIRONMENT != "development"
        or sql.drivername != "postgresql+asyncpg"
        or sql.host not in {"127.0.0.1", "localhost", "::1"}
        or sql.port not in _POSTGRES_F5_PUERTOS
        or sql.database != "pokearena_alembic_frontend_dev"
        or sql.query
        or len(mongo["nodelist"]) != 1
        or mongo["nodelist"][0][0] not in {"127.0.0.1", "localhost", "::1"}
        or mongo["nodelist"][0][1] not in _MONGO_F5_PUERTOS
        or mongo["password"] is None
        or mongo["database"] != MONGO_F5_BASE
        or ajustes.MONGO_DB != MONGO_F5_BASE
        or {k.lower() for k in mongo["options"]} - {"authsource", "directconnection"}
        or mongo["options"].get("directConnection", True) is not True
    ):
        raise ValueError("configuracion_outbox_fuera_de_1f")


def verificar_configuracion(ajustes: Settings) -> None:
    """Conserva el aislamiento 1F y verifica el par exacto de destinos F5."""
    if ajustes.ORIGINAL_RUNTIME != "disabled":
        ajustes.verificar_destinos("outbox")
        if ajustes.OUTBOX_LEASE_SECONDS <= ajustes.DB_CONNECT_TIMEOUT_SECONDS:
            raise ValueError("configuracion_outbox_fuera_de_1f")
        return
    try:
        pg = make_url(ajustes.DATABASE_URL)
        if urlsplit(ajustes.MONGO_URL).scheme != "mongodb":
            raise ValueError()
        mongo = parse_uri(ajustes.MONGO_URL, warn=False)
    except (ArgumentError, PyMongoError, ValueError):
        raise ValueError("configuracion_outbox_fuera_de_1f") from None
    nodos = mongo["nodelist"]
    opciones = mongo["options"]
    if (
        pg.host not in {"127.0.0.1", "::1", "localhost"}
        or pg.port not in {None, 0, 5432, 15433}
        or pg.query
        or not (pg.database or "").startswith("pokearena_alembic_")
        or not pg.username
        or len(nodos) != 1
        or nodos[0][0] not in {"127.0.0.1", "::1", "localhost"}
        or nodos[0][1] not in {None, 0, 27017, 27029}
        or not mongo["username"]
        or "replicaSet" in opciones
        or opciones.get("loadBalanced", False) is not False
        or opciones.get("directConnection", True) is not True
        or ajustes.OUTBOX_LEASE_SECONDS <= ajustes.DB_CONNECT_TIMEOUT_SECONDS
    ):
        raise ValueError("configuracion_outbox_fuera_de_1f")

    if (
        ajustes.MONGO_DB == MONGO_F5_BASE
        or mongo["database"] == MONGO_F5_BASE
        or pg.database == _POSTGRES_F5_BASE
    ):
        try:
            _verificar_f5(ajustes)
        except (ArgumentError, PyMongoError, ValueError):
            raise ValueError("configuracion_outbox_fuera_de_1f") from None
    elif not ajustes.MONGO_DB.startswith(PREFIJOS_MONGO_1F):
        raise ValueError("configuracion_outbox_fuera_de_1f")


async def run_outbox_worker(*, una_vez: bool = False) -> None:
    """Ejecuta un lote o espera entre lotes hasta SIGINT o SIGTERM."""
    ajustes = get_settings()
    verificar_configuracion(ajustes)
    from src.database.postgresql.connection import engine

    if engine.url != make_url(ajustes.DATABASE_URL):
        raise ValueError("configuracion_outbox_fuera_de_1f")
    engine.echo = False

    detener = asyncio.Event()
    senales = (signal.SIGINT, signal.SIGTERM)
    try:
        loop = asyncio.get_running_loop()
        for senal in senales:
            loop.add_signal_handler(senal, detener.set)
    except NotImplementedError:
        pass
    try:
        if ajustes.ORIGINAL_RUNTIME == "outbox":
            await verificar_mongo_original("outbox")
        procesador, almacen, error_temporal = componer_procesador_outbox()
        indices_verificados = False
        while not detener.is_set():
            try:
                if not indices_verificados:
                    await almacen.verificar_indices()
                    indices_verificados = True
                cantidad = await procesador.lote(
                    ajustes.OUTBOX_BATCH_SIZE,
                    ajustes.OUTBOX_CONCURRENCY,
                    detener,
                )
                logger.info("lote_outbox procesados=%d", cantidad)
            except (error_temporal, PyMongoError):
                if una_vez:
                    raise
                logger.warning("lote_outbox no_confirmado")
            if una_vez:
                return
            try:
                await asyncio.wait_for(detener.wait(), timeout=ajustes.OUTBOX_POLL_SECONDS)
            except TimeoutError:
                pass
    finally:
        try:
            for senal in senales:
                loop.remove_signal_handler(senal)
        except (NotImplementedError, NameError):
            pass
        await close_mongo_connection()
        await engine.dispose()


def main() -> int:
    """Ejecuta el worker y sanitiza los fallos de configuración o arranque."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Procesar un solo lote y salir")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Evitar que una configuración DEBUG habilite SQL o parámetros en este proceso.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.CRITICAL)
    try:
        asyncio.run(run_outbox_worker(una_vez=args.once))
    except (ValueError, ValidationError, PyMongoError):
        logger.error("outbox no inició: destino, permisos o índices no verificables")
        return 1
    except Exception:
        logger.error("outbox no completó su ciclo")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
