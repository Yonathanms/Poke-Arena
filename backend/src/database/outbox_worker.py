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


async def sync_location_created(event_payload: dict[str, Any]) -> None:
    """Proyecta una ubicación creada en PostgreSQL hacia la colección locations_catalog de MongoDB."""
    mongo_db = get_mongo_db()
    await mongo_db["locations_catalog"].update_one(
        {"id": event_payload["id"]},
        {"$set": event_payload},
        upsert=True,
    )
    logger.info("Ubicación sincronizada en MongoDB: %s", event_payload.get("id"))


async def process_outbox_batch() -> int:
    """Procesa un lote de eventos pendientes de la tabla outbox_events."""
    from sqlalchemy import text

    async with AsyncWriteSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT id, evento, payload FROM outbox_events"
                " WHERE status = 'PENDING' ORDER BY created_at LIMIT 50"
            )
        )
        events = result.fetchall()

        processed_count = 0
        for event_id, evento, payload in events:
            try:
                # Siguiente paso: despachar evento al proyector correspondiente
                if evento == "CARTA_CREADA":
                    await sync_card_created(payload)
                elif evento == "LocationCreatedEvent":
                    await sync_location_created(payload)

                await session.execute(
                    text(
                        "UPDATE outbox_events SET status = 'PROCESSED', processed_at = NOW()"
                        " WHERE id = :id"
                    ),
                    {"id": str(event_id)},
                )
                processed_count += 1
            except Exception as e:
                logger.error("Error procesando evento %s (%s): %s", event_id, evento, e)

        await session.commit()
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

