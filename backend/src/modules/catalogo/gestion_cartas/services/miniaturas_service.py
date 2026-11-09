"""Lectura de miniaturas del catálogo a través de los puertos existentes."""

from collections.abc import Awaitable, Callable

from ..ports.imagen_ports import AlmacenImagenPort, ArchivoNoExiste, ContenidoInconsistente


async def recuperar_miniatura(
    carta_id: str,
    buscar_referencia: Callable[[str], Awaitable[str | None]],
    almacen: AlmacenImagenPort,
) -> bytes | None:
    """Lee solo el WebP asociado a una miniatura lista."""
    referencia = await buscar_referencia(carta_id)
    if referencia is None:
        return None
    try:
        datos = await almacen.recuperar(referencia)
    except ArchivoNoExiste:
        return None
    if datos[:4] != b"RIFF" or datos[8:12] != b"WEBP":
        raise ContenidoInconsistente("La miniatura no es WebP")
    return datos
