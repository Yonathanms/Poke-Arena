import pytest

from src.modules.content.domain.exceptions import (
    EvolutionCycleError,
    EvolutionSelfReferenceError,
)
from src.modules.content.domain.services.evolution_validation import (
    EvolutionGraphValidator,
    EvolutionRelation,
)


def test_proposed_evolution_with_no_cycle_is_valid() -> None:
    relations = [EvolutionRelation("card-a", "card-b")]

    EvolutionGraphValidator.validate(
        relations,
        EvolutionRelation("card-c", "card-a"),
    )

    assert relations == [EvolutionRelation("card-a", "card-b")]


def test_direct_self_evolution_is_rejected() -> None:
    with pytest.raises(EvolutionSelfReferenceError):
        EvolutionGraphValidator.validate([], EvolutionRelation("card-a", "card-a"))


def test_new_relation_that_closes_two_card_cycle_is_rejected() -> None:
    relations = [EvolutionRelation("card-a", "card-b")]

    with pytest.raises(EvolutionCycleError):
        EvolutionGraphValidator.validate(relations, EvolutionRelation("card-b", "card-a"))

    assert relations == [EvolutionRelation("card-a", "card-b")]


def test_new_relation_that_closes_longer_cycle_is_rejected() -> None:
    relations = [
        EvolutionRelation("card-a", "card-b"),
        EvolutionRelation("card-b", "card-c"),
    ]

    with pytest.raises(EvolutionCycleError):
        EvolutionGraphValidator.validate(relations, EvolutionRelation("card-c", "card-a"))

    assert len(relations) == 2
