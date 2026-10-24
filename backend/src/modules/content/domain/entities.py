from dataclasses import dataclass
from typing import Self

from src.modules.content.domain.exceptions import InvalidCardCostError, InvalidCardPowerError
from src.modules.content.domain.value_objects import (
    AbilitySpec,
    CardRarity,
    CardType,
    LocationEffectSpec,
)
from src.shared.domain.entity import Entity


@dataclass(eq=False)
class Card(Entity):
    """Entidad principal de Carta Pokémon en el Catálogo."""

    code: str = ""
    name: str = ""
    cost: int = 1
    power: int = 0
    card_type: CardType = CardType.INCOLORO
    rarity: CardRarity = CardRarity.COMUN
    image_url: str = ""
    thumbnail_url: str | None = None
    ability: AbilitySpec | None = None

    @classmethod
    def create(
        cls,
        code: str,
        name: str,
        cost: int,
        power: int,
        card_type: CardType,
        rarity: CardRarity,
        image_url: str,
        thumbnail_url: str | None = None,
        ability: AbilitySpec | None = None,
        card_id: str | None = None,
    ) -> Self:
        """Factory method con validaciones de invariantes de dominio."""
        if cost < 1 or cost > 6:
            raise InvalidCardCostError(cost)
        if power < 0:
            raise InvalidCardPowerError(power)

        instance = cls(
            code=code.strip().upper(),
            name=name.strip(),
            cost=cost,
            power=power,
            card_type=card_type,
            rarity=rarity,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            ability=ability,
        )
        if card_id:
            instance.id = card_id
        return instance


@dataclass(eq=False)
class Location(Entity):
    """Entidad de Ubicación donde se juegan las cartas en una partida."""

    name: str = ""
    image_url: str = ""
    thumbnail_url: str | None = None
    effect: LocationEffectSpec | None = None

    @classmethod
    def create(
        cls,
        name: str,
        image_url: str,
        effect: LocationEffectSpec,
        thumbnail_url: str | None = None,
        location_id: str | None = None,
    ) -> Self:
        instance = cls(
            name=name.strip(),
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            effect=effect,
        )
        if location_id:
            instance.id = location_id
        return instance
