from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CardPublicDTO:
    """DTO público inmutable para exponer información de cartas a otros módulos (RNF-ARQ-03)."""

    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    image_url: str
    ability: dict[str, Any] | None


@dataclass(frozen=True)
class LocationPublicDTO:
    """DTO público inmutable para exponer información de ubicaciones a otros módulos."""

    id: str
    name: str
    image_url: str
    effect: dict[str, Any]


class IContentModuleContract(Protocol):
    """
    Contrato público del módulo Content.
    Cualquier otro módulo (ej. Game o Players) sólo puede interactuar a través de esta interfaz.
    """

    async def get_card_by_code(self, code: str) -> CardPublicDTO | None: ...

    async def get_location_by_id(self, location_id: str) -> LocationPublicDTO | None: ...
