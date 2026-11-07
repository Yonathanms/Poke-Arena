"""Representaciones puras; sin ORM, transporte ni flujo de creación de cartas."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Carta:
    """Estado de una carta; identidad/código vienen del futuro caso de uso."""

    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability_id: str
    created_at: datetime
    image_id: str | None = None
    version: int = 1


@dataclass(frozen=True, slots=True)
class Habilidad:
    """Consulta de habilidad existente; params se conserva sin reinterpretar efectos."""

    id: str
    code: str
    name: str
    ability_type: str
    description: str
    params: dict[str, Any]
    has_effect: bool
    evolution_target_card_id: str | None

