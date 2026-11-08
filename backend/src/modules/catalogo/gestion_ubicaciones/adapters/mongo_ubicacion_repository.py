"""Adaptador MongoDB: proyecta ubicación creada en la colección locations_catalog."""
import logging
from typing import Any

from src.database.mongodb.connection import get_mongo_db

logger = logging.getLogger("pokearena.mongo_ubicacion")


class MongoUbicacionRepository:
    async def sincronizar(self, payload: dict[str, Any]) -> None:
        mongo_db = get_mongo_db()
        await mongo_db["locations_catalog"].update_one(
            {"id": payload["id"]},
            {"$set": payload},
            upsert=True,
        )
        logger.info("Ubicación sincronizada en MongoDB: %s", payload.get("id"))
