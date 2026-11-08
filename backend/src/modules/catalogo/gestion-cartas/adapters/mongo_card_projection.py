"""Publicación monotónica de cartas con el cliente PyMongo Async oficial."""

from typing import Any, TypeGuard

from pymongo import ReadPreference
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from src.database.mongodb.destinos_outbox import MONGO_F5_BASE, MONGO_F5_SERVIDOR, PREFIJOS_MONGO_1F

from ..domain.proyeccion_carta import EventoIncompatible, ProyeccionCarta, ProyeccionTemporal


def _entero(valor: object) -> TypeGuard[int]:
    return isinstance(valor, int) and not isinstance(valor, bool)


class MongoProyeccionCartas:
    """Verifica la colección existente y publica por ID estable con mayoría."""

    def __init__(self, coleccion: AsyncCollection[dict[str, Any]]) -> None:
        """Usa la colección inyectada con lecturas primarias y escrituras confirmadas."""
        db = coleccion.database
        if db.name == MONGO_F5_BASE:
            cliente = db.client
            servidores = cliente.topology_description.server_descriptions()
            valido = (
                cliente.options.direct_connection is True
                and cliente.get_default_database(default="_outbox_sin_base").name == MONGO_F5_BASE
                and set(servidores) == {MONGO_F5_SERVIDOR}
            )
        else:
            valido = db.name.startswith(PREFIJOS_MONGO_1F)
        if coleccion.name != "cards_projection" or not valido:
            raise ValueError("destino_mongodb_fuera_de_1f")
        self._coleccion = coleccion.with_options(
            read_preference=ReadPreference.PRIMARY,
            read_concern=ReadConcern("majority"),
            write_concern=WriteConcern(w="majority"),
        )

    async def verificar_indices(self) -> None:
        """Exige el índice único de código, administrado fuera del worker."""
        indices = await self._coleccion.index_information()
        if not any(
            i["key"] == [("code", 1)]
            and i.get("unique")
            and not i.get("sparse")
            and not i.get("partialFilterExpression")
            for i in indices.values()
        ):
            raise ValueError("indice_unico_code_requerido")

    async def guardar(self, carta: ProyeccionCarta) -> None:
        """Inserta o actualiza solo una versión inferior y verifica las colisiones."""
        documento = carta.documento()
        campos = {k: v for k, v in documento.items() if k != "_id"}
        codigo = campos["code"]
        try:
            for _ in range(2):
                try:
                    actualizado = await self._coleccion.update_one(
                        {
                            "_id": carta.id,
                            "aggregate_version": {"$gte": 1, "$lt": carta.version},
                            "$expr": {
                                "$and": [
                                    {"$in": [{"$type": "$aggregate_version"}, ["int", "long"]]},
                                    {"$eq": ["$code", {"$literal": codigo}]},
                                ]
                            },
                        },
                        {"$set": campos},
                    )
                    if actualizado.matched_count:
                        return
                    previo = await self._coleccion.find_one({"_id": carta.id})
                    if previo is None:
                        await self._coleccion.insert_one(dict(documento))
                        return
                except DuplicateKeyError:
                    previo = await self._coleccion.find_one({"_id": carta.id})
                    if previo is None:
                        titular = await self._coleccion.find_one({"code": codigo}, {"_id": 1})
                        if titular is not None and titular["_id"] != carta.id:
                            raise EventoIncompatible("codigo_ocupado_por_otro_id") from None
                        continue
                version = previo.get("aggregate_version")
                if previo.get("code") != codigo or not _entero(version) or version < 1:
                    raise EventoIncompatible("proyeccion_incompatible")
                if version > carta.version:
                    return
                if version == carta.version:
                    if any(
                        previo.get(k) != v or (isinstance(v, int) and not _entero(previo.get(k)))
                        for k, v in campos.items()
                    ):
                        raise EventoIncompatible("version_igual_con_datos_distintos")
                    return
        except PyMongoError:
            raise ProyeccionTemporal("mongodb_no_confirmado") from None
        raise ProyeccionTemporal("escritura_concurrente_no_confirmada")
