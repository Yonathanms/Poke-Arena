"""Validación pura de asociaciones de evolución entre cartas."""

from collections.abc import Sequence
from dataclasses import dataclass

from src.modules.content.domain.exceptions import (
    EvolutionCycleError,
    EvolutionSelfReferenceError,
)


@dataclass(frozen=True)
class EvolutionRelation:
    """Relación dirigida: la carta de origen evoluciona hacia la carta destino."""

    source_card_id: str
    target_card_id: str

    def __post_init__(self) -> None:
        source_card_id = self.source_card_id.strip()
        target_card_id = self.target_card_id.strip()
        if not source_card_id or not target_card_id:
            raise ValueError("Los identificadores de las cartas son obligatorios.")
        object.__setattr__(self, "source_card_id", source_card_id)
        object.__setattr__(self, "target_card_id", target_card_id)


class EvolutionGraphValidator:
    """Valida autorreferencias y ciclos sin consultar ni modificar datos externos."""

    @staticmethod
    def validate(
        existing_relations: Sequence[EvolutionRelation],
        proposed_relation: EvolutionRelation,
    ) -> None:
        source = proposed_relation.source_card_id
        target = proposed_relation.target_card_id

        if source == target:
            raise EvolutionSelfReferenceError(source)

        adjacency: dict[str, list[str]] = {}
        for relation in existing_relations:
            adjacency.setdefault(relation.source_card_id, []).append(relation.target_card_id)

        # Agregar source -> target cerraría un ciclo si ya existe un camino target -> source.
        pending = [target]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == source:
                raise EvolutionCycleError()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency.get(current, ()))
