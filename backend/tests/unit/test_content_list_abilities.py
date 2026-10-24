"""Tests for the local ability picker fallback."""

import pytest

from src.modules.content.application.dtos import AbilityDefinitionDTO
from src.modules.content.application.use_cases.list_abilities import ListCardAbilitiesUseCase
from src.modules.content.domain.value_objects import AbilityCode


class EmptyAbilityRepository:
    async def get_by_code(self, code: AbilityCode) -> AbilityDefinitionDTO | None:
        return None

    async def list_all(self) -> list[AbilityDefinitionDTO]:
        return []

    async def ensure_none_ability(self) -> None:
        return None


@pytest.mark.asyncio
async def test_empty_local_catalog_exposes_explicit_no_ability_option() -> None:
    abilities = await ListCardAbilitiesUseCase(EmptyAbilityRepository()).execute()

    assert len(abilities) == 1
    assert abilities[0].code == "HAB-000"
    assert abilities[0].name == "Sin Habilidad"
    assert abilities[0].trigger is None
