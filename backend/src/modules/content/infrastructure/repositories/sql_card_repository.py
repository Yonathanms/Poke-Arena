from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.application.ports import ICardRepository
from src.modules.content.domain.entities import Card
from src.modules.content.domain.value_objects import (
    AbilitySpec,
    AbilityType,
    CardRarity,
    CardType,
)
from src.modules.content.infrastructure.models import CardModel


class SqlCardRepository(ICardRepository):
    """Repositorio relacional de cartas utilizando SQLAlchemy 2.0 (PostgreSQL)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, card: Card) -> None:
        ability_dict = None
        if card.ability:
            ability_dict = {
                "ability_type": card.ability.ability_type.value,
                "description": card.ability.description,
                "params": card.ability.params,
            }

        model = CardModel(
            id=card.id,
            code=card.code,
            name=card.name,
            cost=card.cost,
            power=card.power,
            card_type=card.card_type.value,
            rarity=card.rarity.value,
            image_url=card.image_url,
            thumbnail_url=card.thumbnail_url,
            ability_spec=ability_dict,
            created_at=card.created_at,
        )
        self.session.add(model)

    async def get_by_id(self, card_id: str) -> Card | None:
        stmt = select(CardModel).where(CardModel.id == card_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_code(self, code: str) -> Card | None:
        stmt = select(CardModel).where(CardModel.code == code.upper())
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    def _to_entity(self, model: CardModel) -> Card:
        ability = None
        if model.ability_spec:
            ability = AbilitySpec(
                ability_type=AbilityType(model.ability_spec.get("ability_type", "HAB-000")),
                description=model.ability_spec.get("description", ""),
                params=model.ability_spec.get("params", {}),
            )

        card = Card.create(
            code=model.code,
            name=model.name,
            cost=model.cost,
            power=model.power,
            card_type=CardType(model.card_type),
            rarity=CardRarity(model.rarity),
            image_url=model.image_url,
            thumbnail_url=model.thumbnail_url,
            ability=ability,
            card_id=model.id,
        )
        card.created_at = model.created_at
        return card
