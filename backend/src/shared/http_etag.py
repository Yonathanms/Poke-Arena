"""Utilidades HTTP condicionales ETag / If-None-Match / 304 Not Modified (RFC 9110, ADR-003)."""

from fastapi import Response


def generar_etag(
    prefijo: str,
    recurso_id: str,
    version: int | str,
    sufijo: str | None = None,
) -> str:
    """Construye un ETag entrecomillado fuerte basado en recurso y versión monotónica."""
    base = f"{prefijo}-{recurso_id}-v{version}"
    if sufijo:
        base = f"{base}-{sufijo}"
    return f'"{base}"'


def _normalizar_etiqueta(etiqueta: str) -> str:
    limpia = etiqueta.strip()
    if limpia.startswith("W/"):
        limpia = limpia[2:].strip()
    return limpia


def coincide_if_none_match(header: str | None, etag: str) -> bool:
    """Evalúa si la cabecera If-None-Match coincide con el ETag vigente según RFC 9110."""
    if not header or not header.strip():
        return False
    objetivo = _normalizar_etiqueta(etag)
    for candidato in header.split(","):
        normalizado = _normalizar_etiqueta(candidato)
        if not normalizado:
            continue
        if normalizado == "*" or normalizado == objetivo:
            return True
    return False


def respuesta_no_modificada(
    etag: str,
    cache_control: str = "private, no-cache",
) -> Response:
    """Devuelve HTTP 304 Not Modified sin cuerpo JSON con ETag y Cache-Control."""
    return Response(
        status_code=304,
        headers={
            "ETag": etag,
            "Cache-Control": cache_control,
        },
    )


construir_etag = generar_etag
coincide_etag = coincide_if_none_match

__all__ = [
    "coincide_etag",
    "coincide_if_none_match",
    "construir_etag",
    "generar_etag",
    "respuesta_no_modificada",
]
