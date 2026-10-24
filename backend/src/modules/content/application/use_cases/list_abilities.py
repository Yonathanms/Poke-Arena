"""Application query for the ability catalog used by card creation."""

from src.modules.content.application.dtos import AbilityCatalogEntryDTO
from src.modules.content.application.ports import IAbilityRepository


class ListCardAbilitiesUseCase:
    def __init__(self, repository: IAbilityRepository) -> None:
        self.repository = repository

    async def execute(self) -> list[AbilityCatalogEntryDTO]:
        definitions = await self.repository.list_all()
        if not definitions:
            # Older local databases may have been created with create_all rather than
            # the catalog-seeding migration. HAB-000 is a domain-defined option and
            # CreateCardUseCase persists it transactionally when selected.
            return [
                AbilityCatalogEntryDTO(
                    code="HAB-000",
                    name="Sin Habilidad",
                    trigger=None,
                    effect=None,
                    affected_card_type=None,
                    parameters={},
                )
            ]
        return [
            AbilityCatalogEntryDTO(
                code=definition.code.value,
                name=definition.name,
                trigger=(
                    definition.ability.ability_type.value
                    if definition.ability is not None
                    else None
                ),
                effect=(definition.ability.description if definition.ability is not None else None),
                affected_card_type=None,
                parameters=(
                    dict(definition.ability.params) if definition.ability is not None else {}
                ),
            )
            for definition in definitions
        ]
