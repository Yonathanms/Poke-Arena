"""Adaptador SQLAlchemy para guardar y reconstruir entidades Card."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.modules.content.application.ports import ICardRepository
from src.modules.content.domain.entities import Card
from src.modules.content.domain.exceptions import (
    AbilityNotFoundError,
    AbilityRequiredError,
)
from src.modules.content.domain.value_objects import (
    AbilityCode,
    AbilitySpec,
    AbilityType,
    CardImageFormat,
    CardImageMetadata,
    CardImageState,
    CardRarity,
    CardThumbnailMetadata,
    CardType,
)
from src.modules.content.infrastructure.models import AbilityModel, CardModel


class SqlCardRepository(ICardRepository):
    """El repositorio comparte la sesión y nunca confirma la transacción."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, card: Card, image_record_id: str | None = None) -> None:
        if card.ability_code is None:
            raise AbilityRequiredError()
        ability_result = await self.session.execute(
            select(AbilityModel).where(AbilityModel.code == card.ability_code.value)
        )
        ability = ability_result.scalar_one_or_none()
        if ability is None:
            raise AbilityNotFoundError(card.ability_code.value)

        # La FK valida la imagen cuando fue incluida; en el sprint puede quedar pendiente.
        model = CardModel(
            id=card.id,
            code=card.code,
            name=card.name,
            cost=card.cost,
            power=card.power,
            card_type=card.card_type.value,
            rarity=card.rarity.value,
            ability_id=ability.id,
            image_id=image_record_id,
            version=1,
            created_at=card.created_at,
        )
        self.session.add(model)
        await self.session.flush()

    async def get_by_id(self, card_id: str) -> Card | None:
        result = await self.session.execute(
            select(CardModel)
            .options(joinedload(CardModel.ability), joinedload(CardModel.image))
            .where(CardModel.id == card_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    async def get_by_code(self, code: str) -> Card | None:
        result = await self.session.execute(
            select(CardModel)
            .options(joinedload(CardModel.ability), joinedload(CardModel.image))
            .where(CardModel.code == code.upper())
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    @staticmethod
    def _to_entity(model: CardModel) -> Card:
        image = model.image
        original_metadata = None
        thumbnail_metadata = None
        if image is not None:
            original_metadata = CardImageMetadata(
                image_format=CardImageFormat(image.image_format),
                byte_size=image.byte_size,
                width=image.width,
                height=image.height,
            )
        if image is not None and image.thumbnail_format is not None:
            if (
                image.thumbnail_byte_size is None
                or image.thumbnail_width is None
                or image.thumbnail_height is None
            ):
                raise ValueError("La miniatura persistida tiene metadatos incompletos.")
            thumbnail_metadata = CardThumbnailMetadata(
                image_format=CardImageFormat(image.thumbnail_format),
                byte_size=image.thumbnail_byte_size,
                width=image.thumbnail_width,
                height=image.thumbnail_height,
            )

        ability_spec = (
            AbilitySpec(
                ability_type=AbilityType(model.ability.ability_type),
                description=model.ability.description,
                params=dict(model.ability.params),
            )
            if model.ability.has_effect
            else None
        )
        card = Card.create(
            code=model.code,
            name=model.name,
            cost=model.cost,
            power=model.power,
            card_type=CardType(model.card_type),
            rarity=CardRarity(model.rarity),
            image_url=image.original_storage_key if image is not None else None,
            thumbnail_url=image.thumbnail_storage_key if image is not None else None,
            ability=ability_spec,
            ability_code=AbilityCode(model.ability.code),
            image_state=CardImageState(image.state) if image is not None else None,
            image_metadata=original_metadata,
            thumbnail_metadata=thumbnail_metadata,
            card_id=model.id,
        )
        card.created_at = model.created_at
        card.version = model.version
        return card
