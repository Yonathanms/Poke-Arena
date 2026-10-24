"""Asignador transaccional de códigos de carta."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.domain.exceptions import (
    CardCodeCapacityExhaustedError,
    CardCodeCounterMissingError,
)
from src.modules.content.domain.value_objects import CardCode, CardType
from src.modules.content.infrastructure.models import CardCodeCounterModel


class SqlCardCodeAllocator:
    """Bloquea y actualiza el contador usando la sesión/UoW del caso de uso."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def allocate_next(self, card_type: CardType) -> CardCode:
        result = await self.session.execute(
            select(CardCodeCounterModel)
            .where(CardCodeCounterModel.card_type == card_type.value)
            .with_for_update()
        )
        counter = result.scalar_one_or_none()
        if counter is None:
            raise CardCodeCounterMissingError(card_type.value)
        if counter.last_value >= 999:
            raise CardCodeCapacityExhaustedError(card_type.value)

        counter.last_value += 1
        await self.session.flush()
        return CardCode(f"PKA-{card_type.value}-{counter.last_value:03d}")
