from dataclasses import dataclass
from typing import Any

from src.modules.content.application.ports import ICardSearchProjectionPort
from src.modules.content.domain.exceptions import (
    InvalidSearchFilterError,
    InvalidSearchRangeError,
)


@dataclass(frozen=True)
class SearchCardsQuery:
    name: str | None = None
    code: str | None = None
    card_type: str | None = None
    cost: int | None = None
    cost_min: int | None = None
    cost_max: int | None = None
    power: int | None = None
    power_min: int | None = None
    power_max: int | None = None
    rarity: str | None = None
    ability_code: str | None = None
    skip: int = 0
    limit: int = 50


@dataclass(frozen=True)
class SearchCardsResult:
    items: list[dict[str, Any]]
    total: int
    skip: int
    limit: int


class SearchCardsUseCase:
    """Caso de Uso: Buscar Carta en el Catálogo (US 2.1.2) sobre MongoDB."""

    def __init__(self, projection_port: ICardSearchProjectionPort) -> None:
        self.projection_port = projection_port

    async def execute(self, query: SearchCardsQuery) -> SearchCardsResult:
        self._validate(query)
        items, total = await self.projection_port.search_cards(
            name=query.name,
            code=query.code,
            card_type=query.card_type,
            cost=query.cost,
            cost_min=query.cost_min,
            cost_max=query.cost_max,
            power=query.power,
            power_min=query.power_min,
            power_max=query.power_max,
            rarity=query.rarity,
            ability_code=query.ability_code,
            skip=query.skip,
            limit=query.limit,
        )
        return SearchCardsResult(
            items=items,
            total=total,
            skip=query.skip,
            limit=query.limit,
        )

    @staticmethod
    def _validate(query: SearchCardsQuery) -> None:
        if query.cost is not None and (query.cost_min is not None or query.cost_max is not None):
            raise InvalidSearchFilterError(
                "cost",
                "No se puede combinar 'cost' con 'cost_min' o 'cost_max'.",
            )
        if query.cost_min is not None and query.cost_max is not None:
            if query.cost_min > query.cost_max:
                raise InvalidSearchRangeError("cost", query.cost_min, query.cost_max)

        if query.power is not None and (query.power_min is not None or query.power_max is not None):
            raise InvalidSearchFilterError(
                "power",
                "No se puede combinar 'power' con 'power_min' o 'power_max'.",
            )
        if query.power_min is not None and query.power_max is not None:
            if query.power_min > query.power_max:
                raise InvalidSearchRangeError("power", query.power_min, query.power_max)
