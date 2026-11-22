"""DTOs Pydantic para búsqueda de partida, heartbeat y oferta de Bot (US 2 y US 3)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IniciarBusquedaRequest(BaseModel):
    """Cuerpo de POST /api/v1/player/matchmaking."""

    model_config = ConfigDict(extra="forbid")

    deck_id: str | None = Field(default=None, max_length=36)
    context: Literal["RANKED", "TOURNAMENT"] = "RANKED"


class BusquedaPartidaDTO(BaseModel):
    """Estado de búsqueda devuelto al jugador autenticado."""

    search_id: str
    status: str
    context: str
    deck_id: str | None
    elo_snapshot: int
    match_id: str | None
    elapsed_seconds: float
    bot_offer_available: bool
    bot_offer_in_seconds: int
    state_version: int
    created_at: datetime
    last_seen_at: datetime
    warning_code: str | None = None
    warning_detail: str | None = None
