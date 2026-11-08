"""Respuesta uniforme de errores sin datos de entrada ni detalles internos."""

import logging
from http import HTTPStatus
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

MEDIA_TYPE = "application/problem+json"
logger = logging.getLogger(__name__)


def problema(
    status: int, codigo: str, mensaje: str, headers: dict[str, str] | None = None
) -> HTTPException:
    """Construye un error HTTP con código estable y mensaje público controlado."""
    return HTTPException(status, {"code": codigo, "detail": mensaje}, headers)


def _respuesta(
    status: int, codigo: str, mensaje: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    correlacion = str(uuid4())
    return JSONResponse(
        status_code=status,
        media_type=MEDIA_TYPE,
        headers={**(headers or {}), "X-Correlation-ID": correlacion},
        content={
            "type": "about:blank",
            "title": HTTPStatus(status).phrase,
            "status": status,
            "detail": mensaje,
            "code": codigo,
            "correlation_id": correlacion,
        },
    )


async def _http(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detalle = exc.detail
    if isinstance(detalle, dict) and "code" in detalle and "detail" in detalle:
        return _respuesta(
            exc.status_code, detalle["code"], detalle["detail"], dict(exc.headers or {})
        )
    return _respuesta(
        exc.status_code, "http_error", "La solicitud no se completó.", dict(exc.headers or {})
    )


async def _validacion(_: Request, exc: Exception) -> JSONResponse:
    return _respuesta(422, "solicitud_invalida", "Verifica los campos y encabezados requeridos.")


async def _inesperado(_: Request, exc: Exception) -> JSONResponse:
    respuesta = _respuesta(500, "error_interno", "La solicitud no se pudo completar.")
    logger.error("Error HTTP inesperado. Correlación %s", respuesta.headers["X-Correlation-ID"])
    return respuesta


def registrar_errores(app: FastAPI) -> None:
    """Registra los handlers de FastAPI sin reutilizar datos sensibles de excepciones."""
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(Exception, _inesperado)


def respuestas_documentadas(descripciones: dict[int, str]) -> dict[int | str, dict[str, object]]:
    """Describe los errores RFC 7807 en las operaciones OpenAPI que los usan."""
    esquema = {
        "type": "object",
        "required": ["type", "title", "status", "detail", "code", "correlation_id"],
        "properties": {
            "type": {"type": "string"},
            "title": {"type": "string"},
            "status": {"type": "integer"},
            "detail": {"type": "string"},
            "code": {"type": "string"},
            "correlation_id": {"type": "string", "format": "uuid"},
        },
    }
    return {
        status: {"description": descripcion, "content": {MEDIA_TYPE: {"schema": esquema}}}
        for status, descripcion in descripciones.items()
    }
