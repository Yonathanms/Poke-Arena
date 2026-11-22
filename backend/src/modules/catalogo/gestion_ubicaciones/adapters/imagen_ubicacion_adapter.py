"""Adaptador Pillow + GridFS: valida proporción 4:3 y guarda WebP en MongoDB GridFS."""
import io

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from gridfs import AsyncGridFSBucket
from gridfs.errors import CorruptGridFile, NoFile
from PIL import Image
from pymongo.errors import PyMongoError

from src.database.mongodb.connection import get_mongo_db
from src.shared.config import get_settings

from ..ports.ubicaciones_ports import ErrorImagenUbicacion, IAlmacenImagenUbicacion

settings = get_settings()

_RATIO_TARGET = 4 / 3
_RATIO_TOLERANCIA = 0.02
_MIN_ANCHO = 800
_MIN_ALTO = 600
_MAX_BYTES = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
_TIPOS_PERMITIDOS = {"image/png", "image/jpeg", "image/webp"}
_THUMB_W, _THUMB_H = 320, 240
_PREFIX = "gridfs:"


class ImagenUbicacionAdapter:
    async def procesar(self, archivo_bytes: bytes, content_type: str) -> tuple[str, str]:
        if content_type not in _TIPOS_PERMITIDOS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato de imagen inválido. Se aceptan PNG, JPG o WebP.",
            )
        if len(archivo_bytes) > _MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La imagen supera el límite de {settings.MAX_IMAGE_SIZE_MB} MB.",
            )

        try:
            imagen = Image.open(io.BytesIO(archivo_bytes))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se pudo leer el archivo de imagen.",
            )

        ancho, alto = imagen.size
        if ancho < _MIN_ANCHO or alto < _MIN_ALTO:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La imagen debe ser al menos {_MIN_ANCHO}×{_MIN_ALTO} píxeles.",
            )
        if abs(ancho / alto - _RATIO_TARGET) > _RATIO_TOLERANCIA:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La imagen debe tener proporción 4:3 exacta.",
            )

        imagen_rgb = imagen.convert("RGB")

        buf_grande = io.BytesIO()
        imagen_rgb.save(buf_grande, format="WEBP", quality=85)
        datos_grande = buf_grande.getvalue()

        miniatura = imagen_rgb.resize((_THUMB_W, _THUMB_H), Image.LANCZOS)
        buf_tablero = io.BytesIO()
        miniatura.save(buf_tablero, format="WEBP", quality=80)
        datos_tablero = buf_tablero.getvalue()

        mongo_db = get_mongo_db()
        bucket = AsyncGridFSBucket(mongo_db, bucket_name="location_images")
        id_grande = await bucket.upload_from_stream("large.webp", datos_grande)
        id_tablero = await bucket.upload_from_stream("thumbnail.webp", datos_tablero)

        return f"{_PREFIX}{id_grande}", f"{_PREFIX}{id_tablero}"


class AlmacenImagenUbicacionGridFS(IAlmacenImagenUbicacion):
    """Recupera imágenes WebP de ubicaciones desde el bucket GridFS location_images."""

    def __init__(
        self,
        bucket: AsyncGridFSBucket | None = None,
        max_bytes: int | None = None,
    ) -> None:
        self._bucket = bucket
        self._max_bytes = max_bytes if max_bytes is not None else _MAX_BYTES

    def _get_bucket(self) -> AsyncGridFSBucket:
        if self._bucket is not None:
            return self._bucket
        return AsyncGridFSBucket(get_mongo_db(), bucket_name="location_images")

    async def recuperar(self, referencia: str) -> bytes | None:
        if not referencia.startswith(_PREFIX):
            return None
        raw_id = referencia.removeprefix(_PREFIX)
        try:
            identificador = ObjectId(raw_id)
        except InvalidId:
            return None
        if referencia != f"{_PREFIX}{identificador}":
            return None

        bucket = self._get_bucket()
        try:
            async with await bucket.open_download_stream(identificador) as archivo:
                longitud = archivo.length
                if not isinstance(longitud, int) or not 0 < longitud <= self._max_bytes:
                    raise ErrorImagenUbicacion("Imagen de ubicación fuera de límites.")
                datos = await archivo.read(self._max_bytes + 1)
                if len(datos) != longitud:
                    raise ErrorImagenUbicacion("Imagen de ubicación inconsistente.")
                return bytes(datos)
        except NoFile:
            return None
        except ErrorImagenUbicacion:
            raise
        except (CorruptGridFile, PyMongoError):
            raise ErrorImagenUbicacion("Imagen de ubicación no disponible.") from None
