"""Adaptador SQL para consultar definiciones del catálogo de habilidades."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.application.dtos import AbilityDefinitionDTO
from src.modules.content.application.ports import IAbilityRepository
from src.modules.content.domain.value_objects import AbilityCode, AbilitySpec, AbilityType
from src.modules.content.infrastructure.models import AbilityModel


class SqlAbilityRepository(IAbilityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_none_ability(self) -> None:
        """Garantiza HAB-000 sin commit y sin duplicar una carga concurrente/repetida."""
        statement = (
            insert(AbilityModel)
            .values(
                id="00000000-0000-0000-0000-000000000000",
                code="HAB-000",
                name="Sin Habilidad",
                ability_type="HAB-000",
                description="",
                params={},
                has_effect=False,
                evolution_target_card_id=None,
            )
            .on_conflict_do_nothing(index_elements=[AbilityModel.code])
        )
        await self.session.execute(statement)
        await self.session.flush()

    async def get_by_code(self, code: AbilityCode) -> AbilityDefinitionDTO | None:
        result = await self.session.execute(
            select(AbilityModel).where(AbilityModel.code == code.value)
        )
        model = result.scalar_one_or_none()
        return self._to_dto(model) if model is not None else None

    async def list_all(self) -> list[AbilityDefinitionDTO]:
        result = await self.session.execute(select(AbilityModel).order_by(AbilityModel.code))
        return [self._to_dto(model) for model in result.scalars().all()]

    @staticmethod
    def _to_dto(model: AbilityModel) -> AbilityDefinitionDTO:
        spec = (
            AbilitySpec(
                ability_type=AbilityType(model.ability_type),
                description=model.description,
                params=dict(model.params),
            )
            if model.has_effect
            else None
        )
        return AbilityDefinitionDTO(code=AbilityCode(model.code), name=model.name, ability=spec)
