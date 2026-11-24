"""Modelos y excepciones puras de dominio para partidas activas (US 4)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


class PartidaError(Exception):
    """Error base del subdominio de partidas."""


class PartidaNoEncontradaError(PartidaError):
    """La partida no existe o el usuario no participa en ella."""


class CatalogoPartidaInvalidoError(PartidaError):
    """Alguna carta del deck ya no existe o no es válida en catálogo."""


class PartidaConflictoActivaError(PartidaError):
    """Alguno de los participantes ya tiene una partida IN_PROGRESS."""


class PartidaNoDisponibleError(PartidaError):
    """Error transitorio de persistencia al consultar o crear la partida."""


@dataclass(frozen=True, slots=True)
class ParticipantePartidaInput:
    """Datos del jugador o bot entregados para iniciar una partida."""

    seat: int
    user_id: str | None
    is_bot: bool
    deck_id: str | None
    card_ids: tuple[str, ...]
    elo: int


@dataclass(frozen=True, slots=True)
class PartidaCreada:
    """Resumen devuelto al confirmar la creación ACID de una partida."""

    match_id: str
    context: str
    status: str
    is_bot_match: bool
    bet_cubes: int
    turn_number: int
    turn_duration_seconds: int
    turn_started_at: datetime
    turn_ends_at: datetime
    state_version: int
    participant_user_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PartidaActivaResumen:
    """Resumen de la partida IN_PROGRESS actual de un jugador."""

    match_id: str
    context: str
    status: str
    is_bot_match: bool
    bet_cubes: int
    turn_number: int
    turn_duration_seconds: int
    turn_started_at: datetime
    turn_ends_at: datetime
    state_version: int


@dataclass(frozen=True, slots=True)
class RegistroPartidaSQL:
    """Registro persistido de una partida recuperada desde PostgreSQL."""

    match_id: str
    context: str
    status: str
    is_bot_match: bool
    bet_cubes: int
    seed: int
    turn_number: int
    turn_duration_seconds: int
    turn_started_at: datetime
    turn_ends_at: datetime
    state_json: dict[str, Any]
    state_version: int
    participant_user_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResultadoVistaPartida:
    """Resultado de lectura condicional (304 Not Modified o vista Fog of War)."""

    not_modified: bool
    etag: str
    state_version: int
    payload: dict[str, Any] | None
