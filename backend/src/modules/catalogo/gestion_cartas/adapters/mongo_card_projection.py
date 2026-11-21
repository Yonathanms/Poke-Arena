"""Adaptador MongoDB para escritura directa y reconciliación de cards_projection."""

import logging
from typing import Any

from pymongo import ReadPreference
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from ..domain.proyeccion_carta import EventoIncompatible, ProyeccionCarta, ProyeccionTemporal

logger = logging.getLogger("pokearena.reconciliador")


class MongoProyeccionCartas:
    """Proyecta cartas confirmadas en MongoDB con escrituras idempotentes."""

    def __init__(self, coleccion: AsyncCollection[dict[str, Any]]) -> None:
        """Configura lecturas primarias y escrituras confirmadas sobre cards_projection."""
        self._coleccion = coleccion.with_options(
            read_preference=ReadPreference.PRIMARY,
            read_concern=ReadConcern("majority"),
            write_concern=WriteConcern(w="majority"),
        )

    async def asegurar_indices(self) -> None:
        """Comprueba el índice único por código y lo crea si el rol tiene permiso."""
        try:
            indices = await self._coleccion.index_information()
            tiene_unico = any(
                i.get("key") == [("code", 1)] and bool(i.get("unique"))
                for i in indices.values()
            )
            if not tiene_unico:
                await self._coleccion.create_index([("code", 1)], unique=True, name="uq_cards_projection_code")
        except OperationFailure as exc:
            logger.debug("No se pudo crear/verificar índice en cards_projection: %s", exc)
        except PyMongoError:
            raise ProyeccionTemporal("mongodb_no_confirmado") from None

    async def guardar(self, carta: ProyeccionCarta) -> None:
        """Inserta o actualiza idempotentemente la proyección desde PostgreSQL."""
        documento = carta.documento()
        campos = {k: v for k, v in documento.items() if k != "_id"}
        try:
            previo = await self._coleccion.find_one({"_id": carta.id})
            if previo is None:
                try:
                    await self._coleccion.insert_one(dict(documento))
                    return
                except DuplicateKeyError:
                    previo = await self._coleccion.find_one({"_id": carta.id})
                    if previo is None:
                        titular = await self._coleccion.find_one(
                            {"code": campos["code"]}, {"_id": 1}
                        )
                        if titular is not None and titular["_id"] != carta.id:
                            raise EventoIncompatible("codigo_ocupado_por_otro_id") from None
                        raise ProyeccionTemporal("escritura_concurrente_no_confirmada") from None

            version_previa = previo.get("aggregate_version")
            if isinstance(version_previa, int) and not isinstance(version_previa, bool):
                if version_previa > carta.version:
                    return

            await self._coleccion.update_one(
                {"_id": carta.id},
                {"$set": campos},
            )
        except EventoIncompatible:
            raise
        except PyMongoError:
            raise ProyeccionTemporal("mongodb_no_confirmado") from None

    async def listar_proyecciones(self) -> dict[str, dict[str, Any]]:
        """Lee todas las proyecciones existentes en cards_projection indexadas por ID."""
        try:
            resultado: dict[str, dict[str, Any]] = {}
            async for doc in self._coleccion.find({}):
                clave = str(doc.get("_id") or doc.get("id") or "")
                if clave:
                    resultado[clave] = doc
            return resultado
        except PyMongoError:
            raise ProyeccionTemporal("mongodb_no_confirmado") from None
