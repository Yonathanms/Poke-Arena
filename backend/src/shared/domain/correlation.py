"""Contenedor de contexto para ID de correlación (RNF-OBS-01).

Permite que el ID de correlación sea accesible por todas las capas
(dominio, aplicación, infraestructura y presentación) sin violar dependencias.
"""

import contextvars

_CORRELATION_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_current_correlation_id() -> str:
    """Retorna el identificador de correlación activo en el contexto actual."""
    return _CORRELATION_ID_CTX.get()


def set_current_correlation_id(correlation_id: str) -> None:
    """Establece el identificador de correlación en el contexto de ejecución."""
    _CORRELATION_ID_CTX.set(correlation_id)
