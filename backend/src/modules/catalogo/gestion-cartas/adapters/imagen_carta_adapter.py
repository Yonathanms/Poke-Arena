"""Validación y miniaturas con Pillow. El original se conserva byte por byte."""

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO

from PIL import Image, ImageOps

from ..domain.imagen_model import (
    MAX_IMAGE_BYTES,
    THUMBNAIL_SIZE,
    ArchivoImagen,
    FormatoImagen,
    ImagenProcesada,
    MetadatosImagen,
    huella_imagen,
)
from ..ports.imagen_ports import (
    ContenidoInconsistente,
    ErrorProcesamiento,
    ImagenInvalida,
    ProcesadorImagenPort,
)

MAX_PIXELS = 20_000_000
MIN_ORIGINAL_SIZE = (600, 840)
FORMATOS = tuple(FormatoImagen)
ERRORES_DECODIFICACION = (OSError, ValueError, SyntaxError, Image.DecompressionBombError)


def _comprobar_cabecera(imagen: Image.Image, miniatura: bool) -> FormatoImagen:
    """Limita píxeles y frames antes de decodificar o transponer."""
    ancho, alto = imagen.size
    if ancho * alto > MAX_PIXELS or getattr(imagen, "n_frames", 1) != 1:
        raise ImagenInvalida("Dimensiones excesivas o imagen con múltiples cuadros")
    if imagen.format is None:
        raise ImagenInvalida("No se pudo identificar el formato")
    formato = FormatoImagen(imagen.format)
    if miniatura and (formato != FormatoImagen.WEBP or imagen.size != THUMBNAIL_SIZE):
        raise ImagenInvalida("La miniatura debe ser WebP de 200 × 280")
    return formato


@contextmanager
def _decodificar(
    datos: bytes, *, miniatura: bool = False
) -> Iterator[tuple[Image.Image, MetadatosImagen]]:
    """Verifica estructura y decodifica. Las dimensiones del original incluyen EXIF."""
    if not 0 < len(datos) <= MAX_IMAGE_BYTES:
        raise ImagenInvalida("El archivo debe contener entre 1 y 5 000 000 bytes")
    formatos = (FormatoImagen.WEBP,) if miniatura else FORMATOS
    try:
        with Image.open(BytesIO(datos), formats=formatos) as inspeccion:
            formato = _comprobar_cabecera(inspeccion, miniatura)
            inspeccion.verify()
        with Image.open(BytesIO(datos), formats=formatos) as fuente:
            fuente.load()
            orientada = ImageOps.exif_transpose(fuente)
    except ERRORES_DECODIFICACION:
        raise ImagenInvalida("Formato no permitido o binario ilegible") from None

    with orientada:
        ancho, alto = orientada.size
        if miniatura and orientada.size != THUMBNAIL_SIZE:
            raise ImagenInvalida("La orientación visual de la miniatura es inválida")
        if not miniatura and (
            ancho < MIN_ORIGINAL_SIZE[0] or alto < MIN_ORIGINAL_SIZE[1] or 7 * ancho != 5 * alto
        ):
            raise ImagenInvalida("Se requiere mínimo 600 × 840 y proporción exacta 5:7")
        yield (
            orientada,
            MetadatosImagen(formato, ancho, alto, len(datos), huella_imagen(datos)),
        )


class ProcesadorImagenPillow(ProcesadorImagenPort):
    """Procesa una imagen estática con un límite de píxeles por llamada."""

    def procesar(self, original: bytes) -> ImagenProcesada:
        """Conserva bytes originales y valida la salida WebP tras volver a abrirla."""
        with _decodificar(original) as (imagen, metadatos):
            try:
                modo = "RGBA" if imagen.has_transparency_data else "RGB"
                with (
                    imagen.convert(modo) as convertida,
                    convertida.resize(
                        THUMBNAIL_SIZE,
                        Image.Resampling.LANCZOS,
                    ) as reducida,
                ):
                    reducida.info.clear()
                    salida = BytesIO()
                    reducida.save(salida, format="WEBP", quality=85, method=4)
                    datos_miniatura = salida.getvalue()
            except (OSError, ValueError):
                raise ErrorProcesamiento("No se pudo generar la miniatura WebP") from None
        try:
            with _decodificar(datos_miniatura, miniatura=True) as (_, meta_miniatura):
                return ImagenProcesada(
                    ArchivoImagen(original, metadatos),
                    ArchivoImagen(datos_miniatura, meta_miniatura),
                )
        except ImagenInvalida:
            raise ErrorProcesamiento("La miniatura generada no es válida") from None

    def verificar(self, imagen: ImagenProcesada) -> None:
        """Valida dimensiones visuales, formato, longitud y hash esperado."""
        if imagen.original.metadatos.sha256 is None:
            raise ContenidoInconsistente("Falta el SHA-256 esperado del original")
        for archivo, miniatura in ((imagen.original, False), (imagen.miniatura, True)):
            try:
                with _decodificar(archivo.datos, miniatura=miniatura) as (_, real):
                    esperado = archivo.metadatos
                    if (
                        (real.formato, real.ancho, real.alto, real.tamano)
                        != (esperado.formato, esperado.ancho, esperado.alto, esperado.tamano)
                        or esperado.sha256 is not None
                        and esperado.sha256 != real.sha256
                    ):
                        raise ContenidoInconsistente("El binario difiere de sus metadatos")
            except ImagenInvalida:
                raise ContenidoInconsistente("El binario recuperado es inválido") from None
