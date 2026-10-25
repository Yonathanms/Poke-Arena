"""Tests unitarios para US-122: Buscar Carta."""

from unittest.mock import AsyncMock, patch

import pytest

from src.modules.content.application.use_cases.search_cards import (
    SearchCardsQuery,
    SearchCardsResult,
    SearchCardsUseCase,
)
from src.modules.content.domain.exceptions import (
    InvalidSearchFilterError,
    InvalidSearchRangeError,
)
from src.modules.content.infrastructure.repositories.mongo_card_projection import (
    MongoCardProjection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CARD = {
    "id": "abc-123",
    "code": "PKA-FUE-001",
    "name": "Charmander",
    "cost": 2,
    "power": 3,
    "card_type": "FUEGO",
    "rarity": "COMUN",
    "image_url": None,
    "thumbnail_url": None,
    "ability": {"code": "HAB-000", "ability_type": "PASIVA", "description": "Sin habilidad", "params": {}},
}


def _make_port(items: list[dict] | None = None, total: int = 0) -> AsyncMock:
    port = AsyncMock()
    port.search_cards.return_value = (items or [], total)
    return port


# ---------------------------------------------------------------------------
# SearchCardsQuery — validación de rangos
# ---------------------------------------------------------------------------


class TestSearchCardsQueryValidation:
    @pytest.mark.parametrize(
        "cost_min, cost_max",
        [(0, 10), (5, 5), (0, 0), (3, 7)],
    )
    @pytest.mark.asyncio
    async def test_valid_cost_range_is_accepted(self, cost_min: int, cost_max: int) -> None:
        port = _make_port()
        use_case = SearchCardsUseCase(port)
        await use_case.execute(SearchCardsQuery(cost_min=cost_min, cost_max=cost_max))
        port.search_cards.assert_called_once()

    @pytest.mark.parametrize(
        "power_min, power_max",
        [(-20, 20), (0, 0), (-5, -5), (-10, 10)],
    )
    @pytest.mark.asyncio
    async def test_valid_power_range_is_accepted(self, power_min: int, power_max: int) -> None:
        port = _make_port()
        use_case = SearchCardsUseCase(port)
        await use_case.execute(SearchCardsQuery(power_min=power_min, power_max=power_max))
        port.search_cards.assert_called_once()

    @pytest.mark.parametrize(
        "cost_min, cost_max",
        [(10, 9), (5, 0), (7, 6)],
    )
    @pytest.mark.asyncio
    async def test_inverted_cost_range_raises_invalid_range_error(
        self, cost_min: int, cost_max: int
    ) -> None:
        use_case = SearchCardsUseCase(_make_port())
        with pytest.raises(InvalidSearchRangeError):
            await use_case.execute(SearchCardsQuery(cost_min=cost_min, cost_max=cost_max))

    @pytest.mark.parametrize(
        "power_min, power_max",
        [(5, -5), (20, -20), (1, 0)],
    )
    @pytest.mark.asyncio
    async def test_inverted_power_range_raises_invalid_range_error(
        self, power_min: int, power_max: int
    ) -> None:
        use_case = SearchCardsUseCase(_make_port())
        with pytest.raises(InvalidSearchRangeError):
            await use_case.execute(SearchCardsQuery(power_min=power_min, power_max=power_max))

    @pytest.mark.asyncio
    async def test_cost_exact_with_cost_min_raises_filter_error(self) -> None:
        use_case = SearchCardsUseCase(_make_port())
        with pytest.raises(InvalidSearchFilterError):
            await use_case.execute(SearchCardsQuery(cost=5, cost_min=3))

    @pytest.mark.asyncio
    async def test_cost_exact_with_cost_max_raises_filter_error(self) -> None:
        use_case = SearchCardsUseCase(_make_port())
        with pytest.raises(InvalidSearchFilterError):
            await use_case.execute(SearchCardsQuery(cost=5, cost_max=8))

    @pytest.mark.asyncio
    async def test_power_exact_with_power_min_raises_filter_error(self) -> None:
        use_case = SearchCardsUseCase(_make_port())
        with pytest.raises(InvalidSearchFilterError):
            await use_case.execute(SearchCardsQuery(power=3, power_min=0))

    @pytest.mark.asyncio
    async def test_power_exact_with_power_max_raises_filter_error(self) -> None:
        use_case = SearchCardsUseCase(_make_port())
        with pytest.raises(InvalidSearchFilterError):
            await use_case.execute(SearchCardsQuery(power=3, power_max=10))


# ---------------------------------------------------------------------------
# SearchCardsUseCase — delegación correcta al puerto
# ---------------------------------------------------------------------------


class TestSearchCardsUseCaseDelegation:
    @pytest.mark.asyncio
    async def test_returns_items_and_pagination(self) -> None:
        port = _make_port(items=[SAMPLE_CARD], total=1)
        use_case = SearchCardsUseCase(port)

        result = await use_case.execute(SearchCardsQuery(skip=0, limit=10))

        assert isinstance(result, SearchCardsResult)
        assert result.total == 1
        assert len(result.items) == 1
        assert result.skip == 0
        assert result.limit == 10

    @pytest.mark.asyncio
    async def test_passes_all_filters_to_port(self) -> None:
        port = _make_port()
        use_case = SearchCardsUseCase(port)

        await use_case.execute(
            SearchCardsQuery(
                name="char",
                code="PKA-FUE-001",
                card_type="FUEGO",
                cost_min=1,
                cost_max=5,
                power_min=-5,
                power_max=10,
                rarity="COMUN",
                ability_code="HAB-001",
                skip=10,
                limit=20,
            )
        )

        port.search_cards.assert_called_once_with(
            name="char",
            code="PKA-FUE-001",
            card_type="FUEGO",
            cost=None,
            cost_min=1,
            cost_max=5,
            power=None,
            power_min=-5,
            power_max=10,
            rarity="COMUN",
            ability_code="HAB-001",
            skip=10,
            limit=20,
        )

    @pytest.mark.asyncio
    async def test_empty_result_returns_zero_total(self) -> None:
        port = _make_port(items=[], total=0)
        use_case = SearchCardsUseCase(port)

        result = await use_case.execute(SearchCardsQuery())

        assert result.total == 0
        assert result.items == []


# ---------------------------------------------------------------------------
# MongoCardProjection._normalize_name — normalización de diacríticos
# ---------------------------------------------------------------------------


class TestNormalizeName:
    @pytest.mark.parametrize(
        "original, expected",
        [
            ("Charmander", "charmander"),
            ("Ñoño", "nono"),
            ("Pokémon", "pokemon"),
            ("Árbol", "arbol"),
            ("Ümlaüt", "umlaut"),
            ("FUEGO", "fuego"),
            ("  espacios  ", "  espacios  "),
        ],
    )
    def test_normalize_strips_diacritics_and_lowercases(
        self, original: str, expected: str
    ) -> None:
        assert MongoCardProjection._normalize_name(original) == expected

    def test_normalize_preserves_non_accented_chars(self) -> None:
        name = "Bulbasaur123"
        assert MongoCardProjection._normalize_name(name) == "bulbasaur123"
