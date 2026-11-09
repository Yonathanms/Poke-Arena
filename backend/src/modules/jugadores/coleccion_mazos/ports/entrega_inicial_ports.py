"""Contratos de la unidad de trabajo de colección inicial."""

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from ..domain.entrega_inicial_model import CartaPaquete, PerfilProvision


class TransaccionEntregaInicial(Protocol):
    """Opera con una sola transacción SQL de beneficios."""

    async def jugador_elegible(self, token_sesion: str) -> str | None:
        """Resuelve el jugador desde una sesión verificada por Identidad."""
        ...

    async def bloquear_perfil(self, usuario_id: str) -> PerfilProvision | None:
        """Serializa la provisión para el perfil."""
        ...

    async def leer_perfil(self, usuario_id: str) -> PerfilProvision | None:
        """Mantiene una lectura coherente mientras se consulta el paquete."""
        ...

    async def cartas_del_paquete(self, usuario_id: str) -> tuple[CartaPaquete, ...]:
        """Lee las cartas asignadas sin elegir nuevas cartas."""
        ...

    async def movimiento_inicial_integro(self, usuario_id: str) -> bool:
        """Comprueba que el historial previo a juego contiene solo el abono inicial."""
        ...

    async def registrar_apertura(self, usuario_id: str) -> datetime:
        """Marca la apertura bajo el bloqueo exclusivo ya adquirido."""
        ...

    async def tiene_inventario_o_historial(self, usuario_id: str) -> bool:
        """Comprueba propiedad o movimientos anteriores bajo el bloqueo del perfil."""
        ...

    async def seleccionar_cartas(self) -> tuple[str, ...]:
        """Sortea hasta quince IDs distintos de cartas elegibles en PostgreSQL."""
        ...

    async def registrar_entrega(self, usuario_id: str, cartas: tuple[str, ...]) -> None:
        """Escribe propiedad, abono, movimiento y marca sin confirmar la transacción."""
        ...


class UnidadEntregaInicial(Protocol):
    """Abre una frontera transaccional para el caso de uso."""

    def transaccion(self) -> AbstractAsyncContextManager[TransaccionEntregaInicial]:
        """Confirma al salir correctamente o revierte al propagar un error."""
        ...
