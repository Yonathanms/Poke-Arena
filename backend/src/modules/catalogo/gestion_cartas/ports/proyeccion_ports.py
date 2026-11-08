"""Dependencias del consumidor de CardCreated."""

from typing import Protocol

from ..domain.proyeccion_carta import EventoReclamado, ProyeccionCarta


class OutboxCartasPort(Protocol):
    """Define transacciones breves para la entrega y su confirmación."""

    async def reclamar(self, limite: int) -> list[EventoReclamado]:
        """Confirma un lote acotado con leases antes de devolverlo."""
        ...

    async def proyeccion(
        self, evento: EventoReclamado, contenido: dict[str, str | int]
    ) -> ProyeccionCarta:
        """Contrasta el snapshot con el agregado SQL y su imagen READY."""
        ...

    async def resolver(
        self, evento: EventoReclamado, error: str | None, demora: int | None = None
    ) -> bool:
        """Confirma éxito, fallo terminal o reintento si el lease sigue vigente."""
        ...


class ProyeccionCartasPort(Protocol):
    """Escribe únicamente en la proyección de catálogo."""

    async def guardar(self, carta: ProyeccionCarta) -> None:
        """Verifica una escritura monotónica o un resultado previo equivalente."""
        ...
