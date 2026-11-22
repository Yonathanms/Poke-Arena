"""Contratos puros del motor de juego consumidos por el módulo de partidas."""

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from ..domain.modelos_partida import (
    EstadoPartidaInterno,
    ParticipanteEntrada,
    UbicacionSnapshot,
)


@runtime_checkable
class MotorJuegoPort(Protocol):
    """Puerto de aplicación para preparar partidas deterministas y proyectar vistas seguras."""

    def preparar_inicio_partida(
        self,
        *,
        seed: int,
        context: str,
        bet_cubes: int,
        ubicaciones_candidatas: Sequence[UbicacionSnapshot],
        jugador_1: ParticipanteEntrada,
        jugador_2: ParticipanteEntrada,
    ) -> EstadoPartidaInterno:
        """Prepara el estado inicial completo de una partida usando la semilla provista."""
        ...

    def proyectar_vista_jugador(
        self,
        estado: EstadoPartidaInterno,
        viewer_user_id: str,
    ) -> dict[str, Any]:
        """Proyecta la vista filtrada por Fog of War para un participante humano."""
        ...


__all__ = ["MotorJuegoPort"]
