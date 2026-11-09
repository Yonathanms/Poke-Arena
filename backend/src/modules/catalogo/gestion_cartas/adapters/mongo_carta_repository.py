"""Almacenamiento GridFS por ID reservado y Repositorio NoSQL de Catálogo."""

from asyncio import to_thread
from re import escape
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from gridfs import AsyncGridFSBucket
from gridfs.errors import CorruptGridFile, FileExists, NoFile
from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, PyMongoError

from src.database.mongodb.connection import get_mongo_db

from ..controllers.cartas_dtos import (
    CartaResponseDTO,
    CartaSearchQueryDTO,
    CartaSearchResponseDTO,
)
from ..domain.imagen_model import (
    MAX_IMAGE_BYTES,
    ArchivoImagen,
    ImagenAlmacenada,
    ImagenProcesada,
    ReferenciasImagen,
)
from ..ports.cartas_ports import ErrorPersistencia, ICartaRepository, TipoErrorPersistencia
from ..ports.imagen_ports import (
    AlmacenImagenPort,
    ArchivoNoExiste,
    ContenidoInconsistente,
    ErrorAlmacenamiento,
    ErrorGuardadoPar,
    ErrorImagen,
    ProcesadorImagenPort,
)

PREFIX = "gridfs:"


def _object_id(referencia: str) -> ObjectId:
    """Acepta únicamente la representación canónica de un ObjectId de GridFS."""
    if not referencia.startswith(PREFIX):
        raise ContenidoInconsistente("Referencia GridFS inválida")
    try:
        identificador = ObjectId(referencia.removeprefix(PREFIX))
    except InvalidId:
        raise ContenidoInconsistente("Referencia GridFS inválida") from None
    if referencia != PREFIX + str(identificador):
        raise ContenidoInconsistente("Referencia GridFS no canónica")
    return identificador


def _error_driver(error: PyMongoError) -> ErrorAlmacenamiento:
    """Clasifica indisponibilidad sin reproducir URL, credenciales ni comandos."""
    return ErrorAlmacenamiento(reintentable=isinstance(error, ConnectionFailure) or error.timeout)


class AlmacenImagenGridFS(AlmacenImagenPort):
    """Opera sobre un bucket inyectado. Un par pertenece a un solo llamador activo."""

    def __init__(self, bucket: AsyncGridFSBucket, procesador: ProcesadorImagenPort) -> None:
        """Recibe el bucket compartido y el verificador de contenido."""
        self._bucket = bucket
        self._procesador = procesador

    def reservar(self) -> ReferenciasImagen:
        """Reserva dos ObjectId antes de escribir para identificar resultados inciertos."""
        return ReferenciasImagen(PREFIX + str(ObjectId()), PREFIX + str(ObjectId()))

    async def recuperar(self, referencia: str) -> bytes:
        """Lee hasta el límite del contrato y comprueba longitud y fragmentos."""
        identificador = _object_id(referencia)
        try:
            async with await self._bucket.open_download_stream(identificador) as archivo:
                longitud = archivo.length
                if not isinstance(longitud, int) or not 0 < longitud <= MAX_IMAGE_BYTES:
                    raise ContenidoInconsistente("Longitud GridFS fuera de los límites")
                datos = await archivo.read(MAX_IMAGE_BYTES + 1)
                if len(datos) != longitud:
                    raise ContenidoInconsistente("Longitud GridFS discordante")
                return datos
        except NoFile:
            raise ArchivoNoExiste("No existe el archivo GridFS solicitado") from None
        except CorruptGridFile:
            raise ContenidoInconsistente("Los fragmentos GridFS son inconsistentes") from None
        except PyMongoError as error:
            raise _error_driver(error) from None

    async def _guardar(self, referencia: str, nombre: str, datos: bytes) -> None:
        """Reutiliza un ID completo solo cuando los bytes coinciden exactamente."""
        try:
            existente = await self.recuperar(referencia)
        except ArchivoNoExiste:
            try:
                await self._bucket.upload_from_stream_with_id(_object_id(referencia), nombre, datos)
            except FileExists:
                raise ContenidoInconsistente("Escritura en conflicto para el ID") from None
            except PyMongoError as error:
                raise _error_driver(error) from None
        else:
            if existente != datos:
                raise ContenidoInconsistente("El ID reservado contiene otros bytes")

    async def guardar_par(
        self,
        referencias: ReferenciasImagen,
        imagen: ImagenProcesada,
    ) -> ImagenAlmacenada:
        """Confirma ambos archivos o expone el progreso. No borra datos ante fallos."""
        if _object_id(referencias.original) == _object_id(referencias.miniatura):
            raise ContenidoInconsistente("Original y miniatura requieren IDs distintos")
        for archivo in (imagen.original, imagen.miniatura):
            if not 0 < len(archivo.datos) <= MAX_IMAGE_BYTES:
                raise ContenidoInconsistente("Binario fuera de los límites de almacenamiento")
        confirmadas: list[str] = []
        try:
            for referencia, nombre, archivo in (
                (referencias.original, "original", imagen.original),
                (referencias.miniatura, "thumbnail.webp", imagen.miniatura),
            ):
                await self._guardar(referencia, nombre, archivo.datos)
                confirmadas.append(referencia)
        except ErrorImagen as error:
            raise ErrorGuardadoPar(referencias, tuple(confirmadas), error) from None
        return ImagenAlmacenada(referencias, imagen.original.metadatos, imagen.miniatura.metadatos)

    async def verificar_par(self, imagen: ImagenAlmacenada) -> None:
        """Contrasta ambos binarios recuperados con los metadatos autoritativos."""
        original = await self.recuperar(imagen.referencias.original)
        miniatura = await self.recuperar(imagen.referencias.miniatura)
        await to_thread(
            self._procesador.verificar,
            ImagenProcesada(
                ArchivoImagen(original, imagen.original),
                ArchivoImagen(miniatura, imagen.miniatura),
            ),
        )

    async def eliminar(self, referencia: str) -> None:
        """Elimina por ID propio confirmado, fuera de cualquier escritura activa."""
        try:
            await self._bucket.delete(_object_id(referencia))
        except NoFile:
            # El driver elimina chunks de ese ID incluso si falta el documento files.
            return
        except PyMongoError as error:
            raise _error_driver(error) from None


class MongoCartaRepository(ICartaRepository):
    """Adaptador de lectura de la proyección oficial de Catálogo."""

    def __init__(self, db: AsyncDatabase[dict[str, Any]] | None = None) -> None:
        self._db = db

    def _get_db(self) -> AsyncDatabase[dict[str, Any]]:
        return get_mongo_db() if self._db is None else self._db

    async def buscar_cartas(self, params: CartaSearchQueryDTO) -> CartaSearchResponseDTO:
        """Interseca filtros y obtiene la página y su total en la misma consulta."""
        query: dict[str, Any] = {}
        termino = (params.q or "").strip()
        if termino:
            patron = {"$regex": escape(termino), "$options": "i"}
            query["$or"] = [
                {campo: patron} for campo in ("name", "code", "description", "descripcion")
            ]
        if params.tipo is not None:
            query["card_type"] = params.tipo.value
        if params.rareza is not None:
            query["rarity"] = params.rareza.value

        pipeline: list[dict[str, Any]] = [{"$match": query}] if query else []
        pipeline.extend([
            {"$sort": {"code": 1, "_id": 1}},
            {"$facet": {
                "items": [
                    {"$skip": (params.pagina - 1) * params.limite}, {"$limit": params.limite},
                ],
                "conteo": [{"$count": "total"}],
            }},
        ])
        try:
            coleccion = self._get_db()["cards_projection"]
            async with await coleccion.aggregate(pipeline) as cursor:
                pagina = await anext(cursor)
            total = pagina["conteo"][0]["total"] if pagina["conteo"] else 0
            return CartaSearchResponseDTO(
                items=[CartaResponseDTO.model_validate(doc) for doc in pagina["items"]],
                total=total,
                pagina=params.pagina,
                limite=params.limite,
                total_paginas=max(1, (total + params.limite - 1) // params.limite),
            )
        except (PyMongoError, ValidationError):
            raise ErrorPersistencia(TipoErrorPersistencia.OPERACION) from None

    async def obtener_por_id_o_codigo(self, identificador: str) -> CartaResponseDTO | None:
        """Lee la ficha real por identificador o código exacto."""
        try:
            doc = await self._get_db()["cards_projection"].find_one({
                "$or": [{"_id": identificador}, {"id": identificador}, {"code": identificador}],
            })
            return CartaResponseDTO.model_validate(doc) if doc is not None else None
        except (PyMongoError, ValidationError):
            raise ErrorPersistencia(TipoErrorPersistencia.OPERACION) from None
