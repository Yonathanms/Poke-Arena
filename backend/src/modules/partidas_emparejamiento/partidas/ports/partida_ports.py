"""Puertos hexagonales del módulo de Partidas."""

from collections.abc import Sequence
from typing import Any, Protocol

from src.modules.motor_juego.domain.modelos_partida import (
    CartaSnapshot,
    EstadoPartidaInterno,
    UbicacionSnapshot,
)

from ..domain.partida_model import (
    ParticipantePartidaInput,
    PartidaActivaResumen,
    PartidaCreada,
    RegistroPartidaSQL,
)


class FuenteCatalogoPartidaPort(Protocol):
    """Puerto hacia Catálogo para leer snapshots inmutables de cartas y ubicaciones."""

    async def leer_cartas_por_ids(
        self, sesion: Any, card_ids: Sequence[str]
    ) -> dict[str, CartaSnapshot]:
        """Obtiene CartaSnapshot indexados por ID para todas las cartas solicitadas."""
        ...

    async def listar_ubicaciones(self, sesion: Any) -> list[UbicacionSnapshot]:
        """Lista todas las ubicaciones elegibles del catálogo."""
        ...

    async def seleccionar_cartas_bot(self, sesion: Any) -> list[CartaSnapshot]:
        """Lista cartas elegibles (con imagen READY) para armar el deck del Bot."""
        ...


class RepositorioPartidasPort(Protocol):
    """Puerto de persistencia ACID para partidas y asientos de jugadores."""

    async def crear_partida_en_sesion(
        self,
        sesion: Any,
        *,
        match_id: str,
        context: str,
        is_bot_match: bool,
        bet_cubes: int,
        seed: int,
        turn_duration_seconds: int,
        estado: EstadoPartidaInterno,
        participantes: tuple[ParticipantePartidaInput, ParticipantePartidaInput],
        decks_snapshots: tuple[list[dict[str, Any]], list[dict[str, Any]]],
    ) -> PartidaCreada:
        """Persiste matches y match_players dentro de la transacción ya abierta."""
        ...

    async def obtener_partida_activa(self, user_id: str) -> PartidaActivaResumen | None:
        """Devuelve la partida IN_PROGRESS del jugador o None."""
        ...

    async def obtener_partida_para_jugador(
        self, user_id: str, match_id: str
    ) -> RegistroPartidaSQL | None:
        """Lee la partida solo si user_id es participante de la misma."""
        ...

    async def deck_en_partida_activa(self, user_id: str, deck_id: str) -> bool:
        """Indica si el deck pertenece a una partida IN_PROGRESS."""
        ...
