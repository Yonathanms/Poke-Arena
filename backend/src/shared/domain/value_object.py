from abc import ABC
from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject(ABC):
    """Clase base inmutable para todos los Value Objects del Dominio."""

    pass
