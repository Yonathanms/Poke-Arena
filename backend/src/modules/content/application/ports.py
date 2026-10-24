from datetime import datetime
from typing import Any, Protocol

from src.modules.content.application.dtos import (
    AbilityCatalogEntryDTO,
    AbilityDefinitionDTO,
    CardCreatedEventDTO,
    CardImageClaimDTO,
    CardImageRecordDTO,
    CardImageStatusDTO,
    ContentAuthenticatedPrincipalDTO,
    IdempotencyRecordDTO,
    OutboxClaimDTO,
)
from src.modules.content.domain.entities import Card, Location
from src.modules.content.domain.value_objects import (
    AbilityCode,
    CardCode,
    CardImageMetadata,
    CardThumbnailMetadata,
    CardType,
)
from src.shared.application.ports import StoredObjectDTO


class ICardRepository(Protocol):
    """Puerto de salida: Persistencia relacional de cartas (PostgreSQL Master)."""

    async def save(self, card: Card, image_record_id: str | None = None) -> None: ...

    async def get_by_id(self, card_id: str) -> Card | None: ...

    async def get_by_code(self, code: str) -> Card | None: ...


class ICardCodeAllocator(Protocol):
    """Puerto para reservar el siguiente código en la transacción activa."""

    async def allocate_next(self, card_type: CardType) -> CardCode: ...


class IAbilityRepository(Protocol):
    """Puerto de lectura de definiciones ya cargadas por catálogo."""

    async def get_by_code(self, code: AbilityCode) -> AbilityDefinitionDTO | None: ...

    async def list_all(self) -> list[AbilityDefinitionDTO]: ...

    async def ensure_none_ability(self) -> None: ...


class IContentAuthorizationPort(Protocol):
    async def authenticate(self, access_token: str) -> ContentAuthenticatedPrincipalDTO: ...


class IAbilityCatalogPort(Protocol):
    async def list_all(self) -> list[AbilityCatalogEntryDTO]: ...


class ICardImageRepository(Protocol):
    """Puerto para guardar y reconstruir el registro de procesamiento de imagen."""

    async def save(self, record: CardImageRecordDTO) -> None: ...

    async def get_by_id(self, image_id: str) -> CardImageRecordDTO | None: ...


class ICardImageProcessingRepository(Protocol):
    async def claim_next(self) -> CardImageClaimDTO | None: ...

    async def renew_lease(self, claim: CardImageClaimDTO) -> CardImageClaimDTO | None: ...

    async def complete(
        self,
        claim: CardImageClaimDTO,
        thumbnail_storage_key: str,
        thumbnail_metadata: CardThumbnailMetadata,
    ) -> CardCreatedEventDTO | None: ...

    async def record_failure(
        self, claim: CardImageClaimDTO, sanitized_error: str
    ) -> CardCreatedEventDTO | None: ...

    async def get_card_image_status(self, card_id: str) -> CardImageStatusDTO | None: ...

    async def requeue_failed(self, card_id: str) -> bool: ...

    async def referenced_storage_keys(self, keys: list[str]) -> set[str]: ...


class ICardCreationIdempotencyPort(Protocol):
    """Reservas transaccionales y consulta de aceptación en el primario."""

    async def acquire_key_guard(self, actor_id: str, operation: str, key: str) -> None: ...

    async def end_preflight_read(self) -> None: ...

    async def release_key_guard(self, actor_id: str, operation: str, key: str) -> None: ...

    async def find(
        self, actor_id: str, operation: str, key: str
    ) -> IdempotencyRecordDTO | None: ...

    async def reserve(self, actor_id: str, operation: str, key: str, request_hash: str) -> bool: ...

    async def complete(
        self,
        actor_id: str,
        operation: str,
        key: str,
        request_hash: str,
        resource_id: str,
        response_body: dict[str, Any],
    ) -> None: ...

    async def find_on_primary(
        self, actor_id: str, operation: str, key: str
    ) -> IdempotencyRecordDTO | None: ...


class IOutboxWriter(Protocol):
    async def add_card_created(self, event: CardCreatedEventDTO) -> None: ...

    async def add_event(self, event: CardCreatedEventDTO) -> None: ...


class IOutboxProcessingRepository(Protocol):
    async def claim_next(self) -> OutboxClaimDTO | None: ...

    async def acknowledge(self, claim: OutboxClaimDTO) -> bool: ...

    async def schedule_retry(self, claim: OutboxClaimDTO, sanitized_error: str) -> bool: ...


class ICardProjectionWriter(Protocol):
    async def project_versioned(self, event: OutboxClaimDTO) -> bool: ...


class ICardImageProcessingTransactions(Protocol):
    """Cortas transacciones de escritura para reclamar y transicionar imágenes."""

    async def claim_next(self) -> CardImageClaimDTO | None: ...

    async def renew_lease(self, claim: CardImageClaimDTO) -> CardImageClaimDTO | None: ...

    async def complete(
        self,
        claim: CardImageClaimDTO,
        thumbnail_storage_key: str,
        thumbnail_metadata: CardThumbnailMetadata,
    ) -> bool: ...

    async def record_failure(self, claim: CardImageClaimDTO, error: str) -> bool: ...

    async def get_status(self, card_id: str) -> CardImageStatusDTO | None: ...

    async def requeue_failed(self, card_id: str) -> bool: ...

    async def referenced_storage_keys(self, keys: list[str]) -> set[str]: ...


class IOutboxProcessingTransactions(Protocol):
    async def claim_next(self) -> OutboxClaimDTO | None: ...

    async def acknowledge(self, claim: OutboxClaimDTO) -> bool: ...

    async def schedule_retry(self, claim: OutboxClaimDTO, error: str) -> bool: ...


class ICardImageInspector(Protocol):
    def inspect_card_image(self, raw_bytes: bytes) -> CardImageMetadata: ...


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

    def make_card_thumbnail(self, raw_bytes: bytes) -> tuple[bytes, CardThumbnailMetadata]: ...

    def validate_and_process_location_image(self, raw_bytes: bytes) -> tuple[bytes, bytes]:
        """Valida aspecto 4:3 y retorna (imagen_procesada, miniatura)."""
        ...


class IImageStoragePort(Protocol):
    """Puerto de salida: Almacenamiento de archivos de imagen (volumen local / Azure Blob)."""

    async def save_file(self, content: bytes, extension: str, subfolder: str = "") -> str:
        """Guarda el binario y retorna la URL/ruta pública relativa del archivo."""
        ...

    async def save_file_at(self, content: bytes, storage_key: str) -> str: ...

    async def delete_file(self, file_url: str) -> None:
        """Elimina el archivo del almacenamiento (rollback de compensación)."""
        ...

    async def read_file(self, storage_key: str) -> bytes: ...

    async def list_files(
        self, subfolder: str, modified_before: datetime
    ) -> list[StoredObjectDTO]: ...


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
