"""Límite de transporte basado en los bytes reales recibidos."""

from collections.abc import AsyncGenerator

from starlette.requests import Request


class CuerpoExcesivo(Exception):
    """El cliente superó el límite de bytes del cuerpo."""


async def flujo_acotado(request: Request, maximo: int) -> AsyncGenerator[bytes, None]:
    """Entrega el flujo hasta el límite, independientemente de Content-Length."""
    total = 0
    async for fragmento in request.stream():
        total += len(fragmento)
        if total > maximo:
            raise CuerpoExcesivo()
        yield fragmento
