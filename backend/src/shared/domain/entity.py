import uuid
from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(eq=False)
class Entity(ABC):
    """Clase base para todas las entidades de dominio."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
