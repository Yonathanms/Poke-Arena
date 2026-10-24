"""Unit tests for durable image and outbox orchestration in Stage 5."""

import hashlib
import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image

from src.modules.content.application.dtos import (
    CardImageClaimDTO,
    CardImageStatusDTO,
    OutboxClaimDTO,
)
from src.modules.content.application.use_cases.process_card_image import ProcessCardImageUseCase
from src.modules.content.application.use_cases.process_durable_work import (
    ProcessOutboxEventUseCase,
    ReconcileImageStorageUseCase,
)
from src.modules.content.domain.value_objects import (
    CardImageFormat,
    CardImageMetadata,
    CardThumbnailMetadata,
)
from src.modules.content.infrastructure.repositories.mongo_card_projection import (
    MongoCardProjection,
)
from src.modules.content.infrastructure.services.pillow_image_processor import PillowImageProcessor
from src.shared.application.ports import StoredObjectDTO


def _raw_image() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (600, 840), "red").save(output, format="PNG")
    return output.getvalue()


class MemoryImageTransactions:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.claim = CardImageClaimDTO(
            image_id="image-1",
            card_id="card-1",
            original_storage_key="/uploads/cards/originals/original.png",
            original_sha256=hashlib.sha256(raw).hexdigest(),
            original_metadata=CardImageMetadata(CardImageFormat.PNG, len(raw), 600, 840),
            attempts=1,
            generation=1,
            lease_token="lease-1",
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
        self.completed: tuple[str, CardThumbnailMetadata] | None = None
        self.failures: list[str] = []

    async def claim_next(self) -> CardImageClaimDTO | None:
        claim, self.claim = self.claim, None
        return claim

    async def renew_lease(self, claim: CardImageClaimDTO) -> CardImageClaimDTO:
        return claim

    async def complete(
        self,
        claim: CardImageClaimDTO,
        thumbnail_storage_key: str,
        thumbnail_metadata: CardThumbnailMetadata,
    ) -> bool:
        self.completed = (thumbnail_storage_key, thumbnail_metadata)
        return True

    async def record_failure(self, claim: CardImageClaimDTO, error: str) -> bool:
        self.failures.append(error)
        return True

    async def get_status(self, card_id: str) -> CardImageStatusDTO | None:
        return None

    async def requeue_failed(self, card_id: str) -> bool:
        return False

    async def referenced_storage_keys(self, keys: list[str]) -> set[str]:
        return set()


class MemoryStorage:
    def __init__(self, original: bytes) -> None:
        self.files = {"/uploads/cards/originals/original.png": original}
        self.deleted: list[str] = []

    async def read_file(self, key: str) -> bytes:
        return self.files[key]

    async def save_file_at(self, content: bytes, key: str) -> str:
        self.files[key] = content
        return key

    async def delete_file(self, key: str) -> None:
        self.deleted.append(key)
        self.files.pop(key, None)

    async def save_file(self, content: bytes, extension: str, subfolder: str = "") -> str:
        raise NotImplementedError

    async def list_files(
        self, subfolder: str, modified_before: datetime
    ) -> list[StoredObjectDTO]:
        return []


@pytest.mark.asyncio
async def test_image_worker_preserves_original_and_publishes_its_attempt_thumbnail() -> None:
    raw = _raw_image()
    transactions = MemoryImageTransactions(raw)
    storage = MemoryStorage(raw)
    processor = PillowImageProcessor()

    did_work = await ProcessCardImageUseCase(
        transactions, storage, processor, processor
    ).execute_once()

    assert did_work is True
    assert storage.files["/uploads/cards/originals/original.png"] == raw
    assert transactions.failures == []
    assert transactions.completed is not None
    key, metadata = transactions.completed
    assert key.startswith("/uploads/cards/thumbnails/image-1/1-lease-1")
    assert metadata.width == 200
    assert metadata.height == 280
    assert key in storage.files


@pytest.mark.asyncio
async def test_corrupted_original_is_retried_without_removing_accepted_original() -> None:
    raw = _raw_image()
    transactions = MemoryImageTransactions(raw)
    storage = MemoryStorage(raw)
    storage.files["/uploads/cards/originals/original.png"] = b"corrupt"
    processor = PillowImageProcessor()

    did_work = await ProcessCardImageUseCase(
        transactions, storage, processor, processor
    ).execute_once()

    assert did_work is True
    assert transactions.completed is None
    assert len(transactions.failures) == 1
    assert "/uploads/cards/originals/original.png" not in storage.deleted
    assert storage.files["/uploads/cards/originals/original.png"] == b"corrupt"


class MemoryOutboxTransactions:
    def __init__(self, claim: OutboxClaimDTO) -> None:
        self.claim = claim
        self.ack_calls = 0
        self.retries: list[str] = []

    async def claim_next(self) -> OutboxClaimDTO:
        return self.claim

    async def acknowledge(self, claim: OutboxClaimDTO) -> bool:
        self.ack_calls += 1
        if self.ack_calls == 1:
            raise ConnectionError("ack uncertainty")
        return True

    async def schedule_retry(self, claim: OutboxClaimDTO, error: str) -> bool:
        self.retries.append(error)
        return True


class VersionedMemoryProjection:
    def __init__(self) -> None:
        self.version = 0
        self.writes = 0

    async def project_versioned(self, event: OutboxClaimDTO) -> bool:
        if event.aggregate_version > self.version:
            self.version = event.aggregate_version
            self.writes += 1
            return True
        return False


@pytest.mark.asyncio
async def test_outbox_replay_after_uncertain_ack_is_version_idempotent() -> None:
    event = OutboxClaimDTO(
        id="event-1",
        event_type="CardImageStateChanged",
        aggregate_id="card-1",
        aggregate_version=2,
        payload={"image_status": "READY"},
        attempts=2,
        lease_token="lease-2",
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )
    transactions = MemoryOutboxTransactions(event)
    projection = VersionedMemoryProjection()
    worker = ProcessOutboxEventUseCase(transactions, projection)

    await worker.execute_once()
    await worker.execute_once()

    assert projection.version == 2
    assert projection.writes == 1
    assert transactions.ack_calls == 2
    assert transactions.retries == []


class AtomicFakeCollection:
    """Models the single Mongo update predicate plus unique _id behavior."""

    def __init__(self) -> None:
        self.document: dict[str, object] | None = None
        self.last_filter: dict[str, object] | None = None

    async def update_one(
        self,
        filter_document: dict[str, object],
        update_document: dict[str, object],
        *,
        upsert: bool,
    ) -> object:
        self.last_filter = filter_document
        assert upsert is True
        assert "_id" in filter_document
        assert "$or" in filter_document
        values = update_document["$set"]
        assert isinstance(values, dict)
        assert "_id" not in values
        version = values["aggregate_version"]
        if self.document is None:
            self.document = dict(values)
            return type("Result", (), {"matched_count": 0, "upserted_id": "card-1"})()
        current_version = self.document["aggregate_version"]
        if version > current_version:
            self.document.update(values)
            return type("Result", (), {"matched_count": 1, "upserted_id": None})()
        from pymongo.errors import DuplicateKeyError

        raise DuplicateKeyError("stale version conflicts on _id")


class AtomicFakeDatabase:
    def __init__(self, collection: AtomicFakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> AtomicFakeCollection:
        return self.collection


@pytest.mark.asyncio
async def test_mongo_projection_uses_atomic_version_predicate_and_ignores_old_event() -> None:
    collection = AtomicFakeCollection()
    projection = MongoCardProjection(AtomicFakeDatabase(collection))  # type: ignore[arg-type]

    for version, state in ((2, "READY"), (1, "PENDING")):
        event = OutboxClaimDTO(
            id=f"event-{version}",
            event_type="CardImageStateChanged",
            aggregate_id="card-1",
            aggregate_version=version,
            payload={"image_status": state},
            attempts=1,
            lease_token=f"lease-{version}",
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
        await projection.project_versioned(event)

    assert collection.document is not None
    assert collection.document["aggregate_version"] == 2
    assert collection.document["image_status"] == "READY"


class ReconciliationTransactions:
    def __init__(self, references: set[str] | Exception) -> None:
        self.references = references

    async def referenced_storage_keys(self, keys: list[str]) -> set[str]:
        if isinstance(self.references, Exception):
            raise self.references
        return self.references


class ReconciliationStorage(MemoryStorage):
    def __init__(self) -> None:
        super().__init__(b"")
        cutoff = datetime.now(UTC) - timedelta(days=2)
        self.candidates = [
            StoredObjectDTO("/uploads/cards/originals/pending.png", cutoff),
            StoredObjectDTO("/uploads/cards/originals/orphan.png", cutoff),
            StoredObjectDTO("/uploads/cards/thumbnails/failed.webp", cutoff),
        ]

    async def list_files(
        self, subfolder: str, modified_before: datetime
    ) -> list[StoredObjectDTO]:
        prefix = f"/uploads/{subfolder}/"
        return [
            item
            for item in self.candidates
            if item.storage_key.startswith(prefix) and item.modified_at < modified_before
        ]


@pytest.mark.asyncio
async def test_reconciliation_deletes_only_proven_aged_orphans() -> None:
    storage = ReconciliationStorage()
    transaction = ReconciliationTransactions(
        {"/uploads/cards/originals/pending.png", "/uploads/cards/thumbnails/failed.webp"}
    )

    removed = await ReconcileImageStorageUseCase(transaction, storage).execute_once()

    assert removed == 1
    assert storage.deleted == ["/uploads/cards/originals/orphan.png"]


@pytest.mark.asyncio
async def test_reconciliation_does_not_delete_when_primary_reference_check_fails() -> None:
    storage = ReconciliationStorage()
    transaction = ReconciliationTransactions(ConnectionError("primary unavailable"))

    with pytest.raises(ConnectionError):
        await ReconcileImageStorageUseCase(transaction, storage).execute_once()

    assert storage.deleted == []
