"""Worker en segundo plano para el patrón Transactional Outbox.

Lee eventos pendientes de sincronización guardados en la tabla 'outbox' de PostgreSQL
y los proyecta hacia MongoDB para mantener el catálogo de búsqueda rápido y actualizado.
"""

import asyncio
import logging
from typing import Any

from src.database.mongodb.connection import get_mongo_db
from src.database.postgresql.connection import AsyncWriteSessionLocal

logger = logging.getLogger("pokearena.outbox_worker")


async def sync_card_created(event_payload: dict[str, Any]) -> None:
    """Proyecta una carta creada en PostgreSQL hacia la colección de MongoDB."""
    mongo_db = get_mongo_db()
    await mongo_db["cards_catalog"].update_one(
        {"code": event_payload["code"]},
        {"$set": event_payload},
        upsert=True,
    )
    logger.info("Carta sincronizada con éxito en MongoDB: %s", event_payload.get("code"))


async def process_outbox_batch() -> int:
    """Procesa un lote de eventos pendientes de la tabla outbox."""
    # En la implementación completa, se leen los registros con processed=False de PostgreSQL,
    # se ejecutan los proyectores correspondientes y se marcan como processed=True.
    async with AsyncWriteSessionLocal() as session:
        _ = session  # Placeholder para la consulta SQL
        processed_count = 0

    return processed_count


async def run_outbox_worker(interval_seconds: float = 5.0) -> None:
    """Bucle infinito para ejecutar el worker periódicamente."""
    logger.info("Worker Outbox iniciado (intervalo: %s segundos)...", interval_seconds)
    while True:
        try:
            await process_outbox_batch()
        except Exception as e:
            logger.error("Error en ciclo del outbox worker: %s", e)
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_outbox_worker())

