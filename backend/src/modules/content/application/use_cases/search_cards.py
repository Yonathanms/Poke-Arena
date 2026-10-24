from dataclasses import dataclass
from typing import Any

from src.modules.content.application.ports import ICardSearchProjectionPort


@dataclass(frozen=True)
class SearchCardsQuery:
    name: str | None = None
    card_type: str | None = None
    cost: int | None = None
    rarity: str | None = None
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
        items, total = await self.projection_port.search_cards(
            name=query.name,
            card_type=query.card_type,
            cost=query.cost,
            rarity=query.rarity,
            skip=query.skip,
            limit=query.limit,
        )
        return SearchCardsResult(
            items=items,
            total=total,
            skip=query.skip,
            limit=query.limit,
        )
