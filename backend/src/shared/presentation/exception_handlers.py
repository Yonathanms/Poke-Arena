import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.shared.domain.correlation import get_current_correlation_id
from src.shared.domain.exceptions import ConflictError, DomainError, EntityNotFoundError

logger = logging.getLogger("pokearena.api")


def _build_error_response(
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    status_code: int = 400,
) -> JSONResponse:
    """Construye el formato estándar de respuesta de error (RFC 7807 / RNF-API-03)."""
    correlation_id = get_current_correlation_id()
    now_iso = datetime.now(UTC).isoformat()

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "correlation_id": correlation_id,
                "timestamp": now_iso,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores de excepciones globales en la aplicación FastAPI."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        cid = get_current_correlation_id()
        logger.warning(f"Domain error [{exc.code}]: {exc.message} - correlation_id={cid}")

        http_status = status.HTTP_400_BAD_REQUEST
        if isinstance(exc, EntityNotFoundError):
            http_status = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ConflictError):
            http_status = status.HTTP_409_CONFLICT
        elif exc.code in {
            "CARD_CREATION_OUTCOME_UNKNOWN",
            "CARD_IMAGE_COMPENSATION_REQUIRED",
        }:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

        return _build_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status_code=http_status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details: list[dict[str, Any]] = []
        for err in exc.errors():
            loc = " -> ".join(str(item) for item in err.get("loc", []))
            details.append(
                {
                    "field": loc,
                    "issue": err.get("msg", "Error de validación"),
                }
            )

        return _build_error_response(
            code="REQUEST_VALIDATION_ERROR",
            message="El cuerpo o los parámetros de la solicitud contienen valores inválidos.",
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            429: "TOO_MANY_REQUESTS",
            503: "SERVICE_UNAVAILABLE",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        response = _build_error_response(
            code=code,
            message=str(exc.detail),
            status_code=exc.status_code,
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            f"Unhandled server error: {str(exc)} - correlation_id={get_current_correlation_id()}"
        )
        return _build_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="Ocurrió un error interno no controlado en el servidor.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
