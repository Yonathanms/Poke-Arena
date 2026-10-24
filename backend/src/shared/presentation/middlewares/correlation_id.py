import contextvars
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

CORRELATION_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_current_correlation_id() -> str:
    """Retorna el ID de correlación activo para la solicitud actual."""
    return CORRELATION_ID_CTX.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware que captura o genera un identificador de correlación único
    por solicitud para trazabilidad y observabilidad (RNF-OBS-01, RNF-OBS-02).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        header_correlation_id = request.headers.get("X-Correlation-ID")
        correlation_id = header_correlation_id or f"req-{uuid.uuid4()}"

        CORRELATION_ID_CTX.set(correlation_id)
        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
