from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.composition import build_card_persistence_adapters
from src.modules.content.domain.exceptions import CardCodeCapacityExhaustedError
from src.modules.content.domain.value_objects import CardType
from src.modules.content.infrastructure.repositories.sql_card_code_allocator import (
    SqlCardCodeAllocator,
)


def test_card_adapters_share_one_sql_session() -> None:
    session = MagicMock(spec=AsyncSession)

    adapters = build_card_persistence_adapters(session)

    assert adapters.uow.session is session
    assert adapters.card_repository.session is session
    assert adapters.code_allocator.session is session
    assert adapters.ability_repository.session is session
    assert adapters.image_repository.session is session


@pytest.mark.asyncio
async def test_allocator_flushes_increment_without_committing() -> None:
    session = AsyncMock(spec=AsyncSession)
    counter = MagicMock(card_type="FUE", last_value=0)
    result = MagicMock()
    result.scalar_one_or_none.return_value = counter
    session.execute.return_value = result

    code = await SqlCardCodeAllocator(session).allocate_next(CardType.FUEGO)

    assert code.value == "PKA-FUE-001"
    assert counter.last_value == 1
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_allocator_does_not_increment_exhausted_counter() -> None:
    session = AsyncMock(spec=AsyncSession)
    counter = MagicMock(card_type="FUE", last_value=999)
    result = MagicMock()
    result.scalar_one_or_none.return_value = counter
    session.execute.return_value = result

    with pytest.raises(CardCodeCapacityExhaustedError):
        await SqlCardCodeAllocator(session).allocate_next(CardType.FUEGO)

    assert counter.last_value == 999
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()
