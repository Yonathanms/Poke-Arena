"""Adaptador MongoDB: proyecta y lee ubicaciones en la colección locations_catalog."""

import logging
from typing import Any

from pymongo import ReadPreference
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from src.database.mongodb.connection import get_mongo_db

from ..ports.ubicaciones_ports import IProyeccionUbicacionRepository

logger = logging.getLogger("pokearena.mongo_ubicacion")


class MongoUbicacionRepository(IProyeccionUbicacionRepository):
    """Gestiona la sincronización directa y lectura de locations_catalog."""

    def __init__(self, coleccion: AsyncCollection[dict[str, Any]] | None = None) -> None:
        self._coleccion = coleccion

    def _get_coleccion(self) -> AsyncCollection[dict[str, Any]]:
        col = self._coleccion if self._coleccion is not None else get_mongo_db()["locations_catalog"]
        return col.with_options(
            read_preference=ReadPreference.PRIMARY,
            read_concern=ReadConcern("majority"),
            write_concern=WriteConcern(w="majority"),
        )

    async def sincronizar(self, payload: dict[str, Any]) -> None:
        """Inserta o actualiza idempotentemente una ubicación en locations_catalog."""
        coleccion = self._get_coleccion()
        await coleccion.update_one(
            {"id": payload["id"]},
            {"$set": dict(payload)},
            upsert=True,
        )
        logger.info("Ubicación sincronizada en MongoDB: %s", payload.get("id"))

    async def listar_proyecciones(self) -> dict[str, dict[str, Any]]:
        """Retorna todas las ubicaciones en locations_catalog indexadas por ID."""
        coleccion = self._get_coleccion()
        resultado: dict[str, dict[str, Any]] = {}
        async for doc in coleccion.find({}):
            clave = str(doc.get("id") or doc.get("_id") or "")
            if clave:
                resultado[clave] = doc
        return resultado
