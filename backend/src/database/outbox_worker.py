"""Punto de entrada independiente para el consumidor CardCreated de 1F."""

import argparse
import asyncio
import logging
import signal
from urllib.parse import urlsplit

from pydantic import ValidationError
from pymongo.errors import PyMongoError

from src.database.mongodb.connection import close_mongo_connection
from src.modules.catalogo.catalogo_module import componer_procesador_outbox
from src.shared.config import Settings, get_settings

logger = logging.getLogger("pokearena.outbox_worker")


def verificar_configuracion(ajustes: Settings) -> None:
    """Limita la ejecución de 1F a destinos explícitos en loopback."""
    pg = urlsplit(ajustes.DATABASE_URL)
    mongo = urlsplit(ajustes.MONGO_URL)
    if (
        pg.hostname not in {"127.0.0.1", "::1", "localhost"}
        or not pg.path.startswith("/pokearena_alembic_")
        or not pg.username
        or mongo.scheme != "mongodb"
        or mongo.hostname not in {"127.0.0.1", "::1", "localhost"}
        or "," in mongo.netloc.rsplit("@", 1)[-1]
        or not mongo.username
        or not ajustes.MONGO_DB.startswith(("pokearena_gridfs_test_", "pokearena_outbox_"))
        or ajustes.OUTBOX_LEASE_SECONDS <= ajustes.DB_CONNECT_TIMEOUT_SECONDS
    ):
        raise ValueError("configuracion_outbox_fuera_de_1f")


async def run_outbox_worker(*, una_vez: bool = False) -> None:
    """Ejecuta un lote o espera entre lotes hasta SIGINT o SIGTERM."""
    ajustes = get_settings()
    verificar_configuracion(ajustes)
    from src.database.postgresql.connection import engine

    engine.echo = False

    detener = asyncio.Event()
    loop = asyncio.get_running_loop()
    senales = (signal.SIGINT, signal.SIGTERM)
    for senal in senales:
        loop.add_signal_handler(senal, detener.set)
    try:
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
        for senal in senales:
            loop.remove_signal_handler(senal)
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
