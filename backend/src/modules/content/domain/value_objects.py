from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.modules.content.domain.exceptions import (
    InvalidAbilityCodeError,
    InvalidCardCodeError,
    InvalidCardImageMetadataError,
    InvalidEnergyBonusError,
    InvalidLocationEffectParamsError,
)
from src.shared.domain.value_object import ValueObject


class CardType(StrEnum):
    FUEGO = "FUE"
    AGUA = "AGU"
    PLANTA = "PLA"
    ELECTRICO = "ELE"
    PSIQUICO = "PSI"
    LUCHA = "LUC"


class CardRarity(StrEnum):
    COMUN = "COMUN"
    POCO_COMUN = "POCO_COMUN"
    RARA = "RARA"
    LEGENDARIA = "LEGENDARIA"


class CardImageState(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    RETRY_PENDING = "RETRY_PENDING"
    READY = "READY"
    FAILED = "FAILED"


class CardImageFormat(StrEnum):
    PNG = "PNG"
    JPEG = "JPEG"
    WEBP = "WEBP"


@dataclass(frozen=True)
class CardCode(ValueObject):
    """Código oficial asignado a una carta, con tipo y consecutivo coherentes."""

    value: str

    def __post_init__(self) -> None:
        parts = self.value.strip().upper().split("-")
        valid_types = {card_type.value for card_type in CardType}
        if (
            len(parts) != 3
            or parts[0] != "PKA"
            or parts[1] not in valid_types
            or len(parts[2]) != 3
            or not parts[2].isascii()
            or not parts[2].isdigit()
            or not 1 <= int(parts[2]) <= 999
        ):
            raise InvalidCardCodeError(self.value)
        object.__setattr__(self, "value", "-".join(parts))

    @property
    def card_type(self) -> CardType:
        return CardType(self.value.split("-")[1])


@dataclass(frozen=True)
class AbilityCode(ValueObject):
    """Código de una definición de habilidad existente, incluida HAB-000."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        parts = normalized.split("-")
        if (
            len(parts) != 2
            or parts[0] != "HAB"
            or len(parts[1]) != 3
            or not parts[1].isascii()
            or not parts[1].isdigit()
        ):
            raise InvalidAbilityCodeError(self.value)
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class CardImageMetadata(ValueObject):
    """Metadatos ya inspeccionados por infraestructura; no abre ni lee archivos."""

    image_format: CardImageFormat
    byte_size: int
    width: int
    height: int

    MIN_WIDTH = 300
    MIN_HEIGHT = 420
    ASPECT_TOLERANCE = 0.05

    def __post_init__(self) -> None:
        if (
            not isinstance(self.image_format, CardImageFormat)
            or self.byte_size < 1
            or self.byte_size > 5_000_000
            or self.width < self.MIN_WIDTH
            or self.height < self.MIN_HEIGHT
            or not self._has_card_aspect(self.width, self.height)
        ):
            raise InvalidCardImageMetadataError(
                byte_size=self.byte_size,
                width=self.width,
                height=self.height,
            )

    @classmethod
    def _has_card_aspect(cls, width: int, height: int) -> bool:
        target_ratio = 5 / 7
        return abs((width / height) / target_ratio - 1) <= cls.ASPECT_TOLERANCE


@dataclass(frozen=True)
class CardThumbnailMetadata(ValueObject):
    """Metadatos de miniatura que el dominio puede comprobar sin abrir el archivo."""

    image_format: CardImageFormat
    byte_size: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.image_format, CardImageFormat)
            or self.image_format is not CardImageFormat.WEBP
            or self.byte_size < 1
            or self.width != 200
            or self.height != 280
        ):
            raise InvalidCardImageMetadataError(
                byte_size=self.byte_size,
                width=self.width,
                height=self.height,
                thumbnail=True,
            )


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


class EnergyBonusMode(StrEnum):
    FIJA = "FIJA"
    POR_CARTAS = "POR_CARTAS"


@dataclass(frozen=True)
class EnergyBonusSpec(ValueObject):
    """Bonificación de energía por turno: fija o proporcional a cartas en ubicación."""

    mode: EnergyBonusMode
    amount: int

    def __post_init__(self) -> None:
        max_val = 3 if self.mode == EnergyBonusMode.FIJA else 2
        if not (0 <= self.amount <= max_val):
            raise InvalidEnergyBonusError(self.mode.value, self.amount, max_val)


@dataclass(frozen=True)
class AbilitySpec(ValueObject):
    """Especificación de habilidad de una carta."""

    ability_type: AbilityType
    description: str
    params: dict[str, Any]


_CATALOG_EFFECT_TYPES = {
    LocationEffectType.BONIFICACION_PODER,
    LocationEffectType.MODIFICADOR_COSTO,
    LocationEffectType.RESTRICCION_TURNO,
}


@dataclass(frozen=True)
class LocationEffectSpec(ValueObject):
    """Especificación de efecto de una ubicación."""

    effect_type: LocationEffectType
    description: str
    params: dict[str, Any]

    @staticmethod
    def validate_params_for_creation(
        effect_type: LocationEffectType, params: dict[str, Any]
    ) -> None:
        """Valida que los parámetros sean correctos para el tipo de efecto dado."""
        if effect_type not in _CATALOG_EFFECT_TYPES:
            raise InvalidLocationEffectParamsError(
                effect_type.value,
                "Tipo de efecto no disponible en el catálogo.",
            )
        valid_card_types = {ct.value for ct in CardType}
        if effect_type == LocationEffectType.BONIFICACION_PODER:
            if params.get("card_type") not in valid_card_types:
                raise InvalidLocationEffectParamsError(
                    effect_type.value,
                    "Se requiere 'card_type' con un tipo válido (FUE, AGU, PLA, ELE, PSI, LUC).",
                )
            amount = params.get("amount")
            if not isinstance(amount, int) or not (-5 <= amount <= 5):
                raise InvalidLocationEffectParamsError(
                    effect_type.value,
                    "Se requiere 'amount' entero en el rango [-5..+5].",
                )
        elif effect_type == LocationEffectType.MODIFICADOR_COSTO:
            amount = params.get("amount")
            if not isinstance(amount, int) or not (-5 <= amount <= 5):
                raise InvalidLocationEffectParamsError(
                    effect_type.value,
                    "Se requiere 'amount' entero en el rango [-5..+5].",
                )
            if "card_type" in params and params["card_type"] not in valid_card_types:
                raise InvalidLocationEffectParamsError(
                    effect_type.value,
                    "Si se indica 'card_type', debe ser un tipo válido (FUE, AGU, PLA, ELE, PSI, LUC).",
                )
        elif effect_type == LocationEffectType.RESTRICCION_TURNO:
            turns = params.get("turns")
            if not isinstance(turns, list) or len(turns) == 0:
                raise InvalidLocationEffectParamsError(
                    effect_type.value,
                    "Se requiere 'turns' como lista no vacía de números de turno.",
                )
            if not all(isinstance(t, int) and t > 0 for t in turns):
                raise InvalidLocationEffectParamsError(
                    effect_type.value,
                    "Cada turno debe ser un entero positivo.",
                )
