"""Almacenamiento GridFS por ID reservado, independiente de estados y transacciones SQL."""

from asyncio import to_thread

from bson import ObjectId
from bson.errors import InvalidId
from gridfs import AsyncGridFSBucket
from gridfs.errors import CorruptGridFile, FileExists, NoFile
from pymongo.errors import ConnectionFailure, PyMongoError

from ..domain.imagen_model import (
    MAX_IMAGE_BYTES,
    ArchivoImagen,
    ImagenAlmacenada,
    ImagenProcesada,
    ReferenciasImagen,
)
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
