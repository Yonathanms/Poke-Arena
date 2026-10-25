from typing import Any

from pydantic import BaseModel, Field

from src.modules.content.domain.value_objects import (
    AbilityType,
    CardImageState,
    CardRarity,
    CardType,
    EnergyBonusMode,
    LocationEffectType,
)


class AbilitySchema(BaseModel):
    ability_type: AbilityType
    description: str
    params: dict[str, Any] = Field(default_factory=dict)


class CardAbilitySummaryResponse(BaseModel):
    code: str
    name: str
    trigger: str | None
    effect: str | None
    affected_card_type: CardType | None
    parameters: dict[str, Any] = Field(default_factory=dict)


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
    image_url: str | None
    thumbnail_url: str | None = None
    ability: CardAbilitySummaryResponse | AbilitySchema | None = None
    image_status: CardImageState | None = None
    available_to_players: bool | None = None
    status_url: str | None = None


class CardCreatedResponse(BaseModel):
    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: CardType
    rarity: CardRarity
    ability: CardAbilitySummaryResponse
    image_status: CardImageState | None
    image_url: str | None
    thumbnail_url: str | None
    available_to_players: bool
    status_url: str


class CardImageStatusResponse(BaseModel):
    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: CardType
    rarity: CardRarity
    ability: CardAbilitySummaryResponse
    image_status: CardImageState | None
    image_url: str | None
    thumbnail_url: str | None
    available_to_players: bool
    status_url: str
    attempts: int = Field(ge=0)
    last_error: str | None


class SearchCardsResponse(BaseModel):
    items: list[CardResponse]
    total: int
    skip: int
    limit: int


class EnergyBonusResponse(BaseModel):
    mode: EnergyBonusMode
    amount: int


class LocationResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    image_url: str
    thumbnail_url: str | None = None
    effect: LocationEffectSchema
    card_limit: int = 5
    energy_bonus: EnergyBonusResponse | None = None
