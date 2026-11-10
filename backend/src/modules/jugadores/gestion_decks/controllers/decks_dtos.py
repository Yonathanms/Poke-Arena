"""DTOs de entrada y salida para los endpoints de decks."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CrearDeckRequest(BaseModel):
    """Cuerpo de POST /player/decks."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100, description="Nombre del deck")
    card_ids: list[str] = Field(..., description="Exactamente 12 IDs de cartas del jugador")


class EditarDeckRequest(BaseModel):
    """Cuerpo de PUT /player/decks/{deck_id}."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100, description="Nombre del deck")
    card_ids: list[str] = Field(..., description="Exactamente 12 IDs de cartas del jugador")


class DeckResumenDTO(BaseModel):
    """Elemento del listado GET /player/decks."""

    id: str
    name: str
    card_count: int
    created_at: datetime


class DeckDetalleDTO(BaseModel):
    """Respuesta de GET /player/decks/{deck_id} — incluye los IDs de cartas."""

    id: str
    name: str
    card_ids: list[str]
    created_at: datetime
