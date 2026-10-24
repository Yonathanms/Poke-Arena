from dataclasses import dataclass
from typing import Self

from src.modules.content.domain.exceptions import (
    AbilityRequiredError,
    CardCodeTypeMismatchError,
    InvalidCardCostError,
    InvalidCardNameError,
    InvalidCardPowerError,
)
from src.modules.content.domain.value_objects import (
    AbilityCode,
    AbilitySpec,
    CardCode,
    CardImageMetadata,
    CardImageState,
    CardRarity,
    CardThumbnailMetadata,
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
    card_type: CardType = CardType.FUEGO
    rarity: CardRarity = CardRarity.COMUN
    image_url: str = ""
    thumbnail_url: str | None = None
    ability: AbilitySpec | None = None
    ability_code: AbilityCode | None = None
    image_state: CardImageState = CardImageState.PENDING
    image_metadata: CardImageMetadata | None = None
    thumbnail_metadata: CardThumbnailMetadata | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.ability_code is None:
            raise AbilityRequiredError()

    @classmethod
    def validate_fields(
        cls, name: str, cost: int, power: int, ability_code: AbilityCode | None
    ) -> str:
        """Valida campos antes de que la aplicación reserve un código."""
        if cost < 0 or cost > 10:
            raise InvalidCardCostError(cost)
        if power < -20 or power > 20:
            raise InvalidCardPowerError(power)
        if ability_code is None:
            raise AbilityRequiredError()
        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > 100:
            raise InvalidCardNameError()
        return normalized_name

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
        ability_code: AbilityCode | None = None,
        image_state: CardImageState = CardImageState.PENDING,
        image_metadata: CardImageMetadata | None = None,
        thumbnail_metadata: CardThumbnailMetadata | None = None,
        card_id: str | None = None,
        version: int = 1,
    ) -> Self:
        """Construye una carta comprobando sus invariantes de dominio."""
        normalized_name = cls.validate_fields(name, cost, power, ability_code)

        card_code = CardCode(code)
        if card_code.card_type != card_type:
            raise CardCodeTypeMismatchError(card_code.value, card_type.value)

        instance = cls(
            code=card_code.value,
            name=normalized_name,
            cost=cost,
            power=power,
            card_type=card_type,
            rarity=rarity,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            ability=ability,
            ability_code=ability_code,
            image_state=image_state,
            image_metadata=image_metadata,
            thumbnail_metadata=thumbnail_metadata,
            version=version,
        )
        if card_id:
            instance.id = card_id
        return instance

    @property
    def available_to_players(self) -> bool:
        """La disponibilidad depende del estado y de referencias/metadatos válidos."""
        return (
            self.image_state is CardImageState.READY
            and bool(self.image_url.strip())
            and bool(self.thumbnail_url and self.thumbnail_url.strip())
            and self.image_metadata is not None
            and self.thumbnail_metadata is not None
        )


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
