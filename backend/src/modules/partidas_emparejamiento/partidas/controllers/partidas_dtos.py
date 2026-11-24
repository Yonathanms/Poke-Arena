"""DTOs Pydantic de respuesta para endpoints de partidas activas (US 4)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PartidaActivaDTO(BaseModel):
    """Resumen ligero de la partida activa actual del jugador."""

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


class EnergiaVistaDTO(BaseModel):
    """Desglose de energía del turno actual del jugador."""

    total: int
    base: int
    bonus: int


class CartaPartidaDTO(BaseModel):
    """Snapshot público de una carta visible para el jugador."""

    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability_code: str
    ability_name: str
    ability_params: dict[str, Any]


class UbicacionPartidaDTO(BaseModel):
    """Snapshot público de una ubicación en el tablero de partida."""

    id: str
    nombre: str
    descripcion: str
    card_limit: int
    energia_tipo: str
    energia_valor: int
    efecto_tipo: str
    efecto_params: dict[str, Any]
    image_url: str
    thumbnail_url: str
    my_cards: list[CartaPartidaDTO]
    opponent_cards: list[CartaPartidaDTO]


class RivalPartidaDTO(BaseModel):
    """Información pública del oponente bajo Fog of War (nunca mano ni mazo)."""

    seat: int
    is_bot: bool
    elo: int
    hand_count: int
    deck_remaining: int
    graveyard: list[CartaPartidaDTO]


class VistaPartidaDTO(BaseModel):
    """Vista autoritativa Fog of War de la partida para el jugador autenticado."""

    match_id: str
    status: str
    context: str
    is_bot_match: bool
    bet_cubes: int
    turn_number: int
    turn_duration_seconds: int
    turn_started_at: datetime
    turn_ends_at: datetime
    state_version: int
    my_seat: int
    locations: list[UbicacionPartidaDTO]
    my_hand: list[CartaPartidaDTO]
    my_deck_remaining: int
    my_graveyard: list[CartaPartidaDTO]
    my_energy: EnergiaVistaDTO
    opponent: RivalPartidaDTO
