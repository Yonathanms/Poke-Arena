"""Contratos hexagonales para proyección directa y reconciliación de cartas."""

from typing import Any, Protocol

from ..domain.proyeccion_carta import ProyeccionCarta


class FuenteCartasSqlPort(Protocol):
    """Lee el estado autoritativo de cartas listas desde PostgreSQL."""

    async def listar_cartas_listas(self) -> list[ProyeccionCarta]:
        """Retorna todas las cartas confirmadas con imagen en estado READY."""
        ...


class ProyeccionCartasPort(Protocol):
    """Gestiona la proyección de lectura de cartas en MongoDB."""

    async def asegurar_indices(self) -> None:
        """Verifica o crea el índice único por código en cards_projection."""
        ...

    async def guardar(self, carta: ProyeccionCarta) -> None:
        """Inserta o actualiza idempotentemente la carta en MongoDB."""
        ...

    async def listar_proyecciones(self) -> dict[str, dict[str, Any]]:
        """Obtiene los documentos existentes en MongoDB indexados por ID."""
        ...
