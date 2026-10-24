from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.shared.domain.value_object import ValueObject


class CardType(StrEnum):
    FUEGO = "FUE"
    AGUA = "AGU"
    PLANTA = "PLA"
    ELECTRICO = "ELE"
    PSIQUICO = "PSI"
    LUCHA = "LUC"
    INCOLORO = "INC"


class CardRarity(StrEnum):
    COMUN = "COMUN"
    POCO_COMUN = "POCO_COMUN"
    RARA = "RARA"
    EPICA = "EPICA"
    LEGENDARIA = "LEGENDARIA"


class AbilityType(StrEnum):
    NINGUNA = "HAB-000"
    AL_REVELARSE = "AL_REVELARSE"
    EFECTO_CONTINUO = "EFECTO_CONTINUO"
    EVOLUCION = "EVOLUCION"


class LocationEffectType(StrEnum):
    BONIFICACION_PODER = "BONIFICACION_PODER"
    MODIFICADOR_COSTO = "MODIFICADOR_COSTO"
    RESTRICCION_TURNO = "RESTRICCION_TURNO"
    LIMITE_CARTAS = "LIMITE_CARTAS"


@dataclass(frozen=True)
class AbilitySpec(ValueObject):
    """Especificación de habilidad de una carta."""

    ability_type: AbilityType
    description: str
    params: dict[str, Any]


@dataclass(frozen=True)
class LocationEffectSpec(ValueObject):
    """Especificación de efecto de una ubicación."""

    effect_type: LocationEffectType
    description: str
    params: dict[str, Any]
