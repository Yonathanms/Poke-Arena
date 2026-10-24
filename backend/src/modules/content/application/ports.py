from typing import Any, Protocol

from src.modules.content.domain.entities import Card, Location


class ICardRepository(Protocol):
    """Puerto de salida: Persistencia relacional de cartas (PostgreSQL Master)."""

    async def save(self, card: Card) -> None: ...

    async def get_by_id(self, card_id: str) -> Card | None: ...

    async def get_by_code(self, code: str) -> Card | None: ...


class ILocationRepository(Protocol):
    """Puerto de salida: Persistencia relacional de ubicaciones (PostgreSQL Master)."""

    async def save(self, location: Location) -> None: ...

    async def get_by_id(self, location_id: str) -> Location | None: ...

    async def list_all(self) -> list[Location]: ...


class IImageProcessorPort(Protocol):
    """Puerto de salida: Procesamiento y validación de relaciones de aspecto de imagen."""

    def validate_and_process_card_image(self, raw_bytes: bytes) -> tuple[bytes, bytes]:
        """Valida aspecto 5:7 y retorna (imagen_procesada, miniatura)."""
        ...

    def validate_and_process_location_image(self, raw_bytes: bytes) -> tuple[bytes, bytes]:
        """Valida aspecto 4:3 y retorna (imagen_procesada, miniatura)."""
        ...


class ICardSearchProjectionPort(Protocol):
    """Puerto de salida: Proyecciones de lectura rápida en MongoDB (RNF-ALM-01, US 2.1.2)."""

    async def sync_card_projection(self, card: Card) -> None:
        """Sincroniza el documento desnormalizado de la carta en MongoDB."""
        ...

    async def search_cards(
        self,
        name: str | None = None,
        card_type: str | None = None,
        cost: int | None = None,
        rarity: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Busca cartas aplicando filtros sin joins sobre MongoDB. Retorna (items, total)."""
        ...
