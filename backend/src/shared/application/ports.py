"""Puertos abstractos del Kernel Compartido."""

from typing import Any, Protocol


class IIdempotencyService(Protocol):
    """Puerto de aplicación para el manejo de idempotencia en solicitudes HTTP."""

    async def get_recorded_response(
        self, idempotency_key: str, endpoint: str
    ) -> dict[str, Any] | None:
        """Retorna la respuesta almacenada si la llave ya fue procesada."""
        ...

    async def record_response(
        self,
        idempotency_key: str,
        endpoint: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None:
        """Almacena la respuesta generada para solicitudes idénticas futuras."""
        ...
