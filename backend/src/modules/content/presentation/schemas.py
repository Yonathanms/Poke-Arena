from typing import Any

from pydantic import BaseModel, Field

from src.modules.content.domain.value_objects import (
    AbilityType,
    CardRarity,
    CardType,
    LocationEffectType,
)


class AbilitySchema(BaseModel):
    ability_type: AbilityType
    description: str
    params: dict[str, Any] = Field(default_factory=dict)


class LocationEffectSchema(BaseModel):
    effect_type: LocationEffectType
    description: str
    params: dict[str, Any] = Field(default_factory=dict)


class CardResponse(BaseModel):
    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: CardType
    rarity: CardRarity
    image_url: str
    thumbnail_url: str | None = None
    ability: AbilitySchema | None = None


class CardAbilitySummaryResponse(BaseModel):
    code: str
    name: str
    trigger: str | None
    effect: str | None
    affected_card_type: CardType | None
    parameters: dict[str, Any] = Field(default_factory=dict)


class CardCreatedResponse(BaseModel):
    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: CardType
    rarity: CardRarity
    ability: CardAbilitySummaryResponse
    image_status: str
    image_url: str | None
    thumbnail_url: str | None
    available_to_players: bool
    status_url: str


class SearchCardsResponse(BaseModel):
    items: list[CardResponse]
    total: int
    skip: int
    limit: int


class LocationResponse(BaseModel):
    id: str
    name: str
    image_url: str
    thumbnail_url: str | None = None
    effect: LocationEffectSchema
