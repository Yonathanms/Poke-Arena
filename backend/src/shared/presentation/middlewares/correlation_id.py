import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.shared.domain.correlation import set_current_correlation_id


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

        set_current_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
