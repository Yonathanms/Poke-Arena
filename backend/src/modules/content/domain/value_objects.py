from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.modules.content.domain.exceptions import (
    InvalidAbilityCodeError,
    InvalidCardCodeError,
    InvalidCardImageMetadataError,
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

    def __post_init__(self) -> None:
        if (
            not isinstance(self.image_format, CardImageFormat)
            or self.byte_size < 1
            or self.byte_size > 5_000_000
            or self.width < 600
            or self.height < 840
            or self.width * 7 != self.height * 5
        ):
            raise InvalidCardImageMetadataError(
                byte_size=self.byte_size,
                width=self.width,
                height=self.height,
            )


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
