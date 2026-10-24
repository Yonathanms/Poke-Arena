"""DTOs de aplicación para persistencia, sin filtrar modelos o sesiones SQL."""

from dataclasses import dataclass
from datetime import datetime

from src.modules.content.domain.value_objects import (
    AbilityCode,
    AbilitySpec,
    CardImageMetadata,
    CardImageState,
    CardThumbnailMetadata,
)

type JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True)
class AbilityDefinitionDTO:
    code: AbilityCode
    name: str
    ability: AbilitySpec | None


@dataclass(frozen=True)
class CardImageRecordDTO:
    id: str
    original_storage_key: str
    original_sha256: str
    original_metadata: CardImageMetadata
    state: CardImageState = CardImageState.PENDING
    thumbnail_storage_key: str | None = None
    thumbnail_metadata: CardThumbnailMetadata | None = None
    attempts: int = 0
    generation: int = 0
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    next_attempt_at: datetime | None = None
    sanitized_error: str | None = None


@dataclass(frozen=True)
class CardImageClaimDTO:
    image_id: str
    card_id: str
    original_storage_key: str
    original_sha256: str
    original_metadata: CardImageMetadata
    attempts: int
    generation: int
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class CardImageStatusDTO:
    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability: dict[str, JsonValue]
    image_status: str
    image_url: str | None
    thumbnail_url: str | None
    available_to_players: bool
    status_url: str
    attempts: int
    last_error: str | None
    version: int


@dataclass(frozen=True)
class OutboxClaimDTO:
    id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    payload: dict[str, JsonValue]
    attempts: int
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class IdempotencyRecordDTO:
    actor_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    resource_id: str | None
    response_status: int | None
    response_body: dict[str, JsonValue] | None


@dataclass(frozen=True)
class CardCreatedEventDTO:
    event_id: str
    aggregate_id: str
    aggregate_version: int
    correlation_id: str
    payload: dict[str, JsonValue]
    event_type: str = "CardCreated"


@dataclass(frozen=True)
class CardCreationSnapshot:
    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability: dict[str, JsonValue]
    image_status: str
    image_url: str | None
    thumbnail_url: str | None
    available_to_players: bool
    status_url: str

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "cost": self.cost,
            "power": self.power,
            "card_type": self.card_type,
            "rarity": self.rarity,
            "ability": self.ability,
            "image_status": self.image_status,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "available_to_players": self.available_to_players,
            "status_url": self.status_url,
        }


@dataclass(frozen=True)
class CreateCardResult:
    snapshot: CardCreationSnapshot
    replayed: bool = False
