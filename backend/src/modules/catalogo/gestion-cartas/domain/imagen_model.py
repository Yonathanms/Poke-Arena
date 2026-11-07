"""Datos de imagen compartidos por procesamiento, GridFS y el futuro caso de uso."""

from dataclasses import dataclass, field
from enum import StrEnum

MAX_IMAGE_BYTES = 5_000_000
THUMBNAIL_SIZE = (200, 280)


class FormatoImagen(StrEnum):
    """Formatos detectados a partir del contenido."""

    PNG = "PNG"
    JPEG = "JPEG"
    WEBP = "WEBP"


@dataclass(frozen=True, slots=True)
class MetadatosImagen:
    """Dimensiones visuales y tamaño real. SQL conserva SHA-256 del original."""

    formato: FormatoImagen
    ancho: int
    alto: int
    tamano: int
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ArchivoImagen:
    """Binario en memoria y metadatos medidos."""

    datos: bytes = field(repr=False)
    metadatos: MetadatosImagen


@dataclass(frozen=True, slots=True)
class ImagenProcesada:
    """Original intacto y miniatura generada a partir de su orientación visual."""

    original: ArchivoImagen
    miniatura: ArchivoImagen


@dataclass(frozen=True, slots=True)
class ReferenciasImagen:
    """IDs reservados para una sola operación, serializables en SQL."""

    original: str
    miniatura: str


@dataclass(frozen=True, slots=True)
class ImagenAlmacenada:
    """Referencias y metadatos para el futuro registro SQL."""

    referencias: ReferenciasImagen
    original: MetadatosImagen
    miniatura: MetadatosImagen
