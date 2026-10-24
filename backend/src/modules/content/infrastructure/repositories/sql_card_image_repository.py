"""SQL persistence for card images and recoverable processing leases."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.modules.content.application.dtos import (
    CardCreatedEventDTO,
    CardImageClaimDTO,
    CardImageRecordDTO,
    CardImageStatusDTO,
    JsonValue,
)
from src.modules.content.application.ports import ICardImageRepository
from src.modules.content.domain.value_objects import (
    CardImageFormat,
    CardImageMetadata,
    CardImageState,
    CardThumbnailMetadata,
)
from src.modules.content.infrastructure.models import CardImageModel, CardModel
from src.shared.infrastructure.models import OutboxModel


class SqlCardImageRepository(ICardImageRepository):
    """Repository methods flush only; caller UoWs own every commit and rollback."""

    RETRY_DELAYS = {1: 2, 2: 10, 3: 30, 4: 120}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, record: CardImageRecordDTO) -> None:
        original = record.original_metadata
        thumbnail = record.thumbnail_metadata
        model = CardImageModel(
            id=record.id,
            original_storage_key=record.original_storage_key,
            original_sha256=record.original_sha256,
            image_format=original.image_format.value,
            byte_size=original.byte_size,
            width=original.width,
            height=original.height,
            thumbnail_storage_key=record.thumbnail_storage_key,
            thumbnail_format=thumbnail.image_format.value if thumbnail else None,
            thumbnail_byte_size=thumbnail.byte_size if thumbnail else None,
            thumbnail_width=thumbnail.width if thumbnail else None,
            thumbnail_height=thumbnail.height if thumbnail else None,
            state=record.state.value,
            attempts=record.attempts,
            generation=record.generation,
            lease_token=record.lease_token,
            lease_expires_at=record.lease_expires_at,
            next_attempt_at=record.next_attempt_at,
            sanitized_error=record.sanitized_error,
        )
        self.session.add(model)
        await self.session.flush()

    async def get_by_id(self, image_id: str) -> CardImageRecordDTO | None:
        result = await self.session.execute(
            select(CardImageModel).where(CardImageModel.id == image_id)
        )
        model = result.scalar_one_or_none()
        return self._to_dto(model) if model is not None else None

    async def claim_next(self) -> CardImageClaimDTO | None:
        now = func.now()
        await self._fail_exhausted_expired_leases()
        eligible = (
            (CardImageModel.state == CardImageState.PENDING.value)
            | (
                (CardImageModel.state == CardImageState.RETRY_PENDING.value)
                & (CardImageModel.next_attempt_at <= now)
            )
            | (
                (CardImageModel.state == CardImageState.PROCESSING.value)
                & (CardImageModel.lease_expires_at <= now)
            )
        )
        result = await self.session.execute(
            select(CardImageModel, CardModel.id)
            .join(CardModel, CardModel.image_id == CardImageModel.id)
            .where(eligible, CardImageModel.attempts < 5)
            .order_by(CardImageModel.created_at, CardImageModel.id)
            .with_for_update(skip_locked=True, of=CardImageModel)
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            return None
        model, card_id = row
        model.state = CardImageState.PROCESSING.value
        model.attempts += 1
        model.generation += 1
        model.lease_token = str(uuid.uuid4())
        model.lease_expires_at = await self.session.scalar(
            select(func.now() + text("interval '60 seconds'"))
        )
        model.next_attempt_at = None
        model.updated_at = datetime.now(UTC)
        await self.session.flush()
        return self._claim_dto(model, card_id)

    async def _fail_exhausted_expired_leases(self) -> None:
        result = await self.session.execute(
            select(CardImageModel, CardModel.id)
            .join(CardModel, CardModel.image_id == CardImageModel.id)
            .where(
                CardImageModel.state == CardImageState.PROCESSING.value,
                CardImageModel.attempts >= 5,
                CardImageModel.lease_expires_at <= func.now(),
            )
            .with_for_update(skip_locked=True, of=CardImageModel)
            .limit(50)
        )
        for image, card_id in result.all():
            image.state = CardImageState.FAILED.value
            image.lease_token = None
            image.lease_expires_at = None
            image.sanitized_error = "Lease vencido después del quinto intento."
            image.updated_at = datetime.now(UTC)
            version = await self._increment_card_version(card_id)
            card_model = await self._get_card_model(card_id)
            if card_model is None:
                raise RuntimeError("La carta asociada a la imagen ya no existe.")
            event = self._make_event(card_model, version, "CardImageStateChanged")
            self.session.add(self._outbox_model(event))
        await self.session.flush()

    async def renew_lease(self, claim: CardImageClaimDTO) -> CardImageClaimDTO | None:
        now = func.now()
        result = await self.session.execute(
            update(CardImageModel)
            .where(
                CardImageModel.id == claim.image_id,
                CardImageModel.state == CardImageState.PROCESSING.value,
                CardImageModel.lease_token == claim.lease_token,
                CardImageModel.generation == claim.generation,
                CardImageModel.lease_expires_at > now,
            )
            .values(lease_expires_at=now + text("interval '60 seconds'"), updated_at=now)
            .returning(CardImageModel.lease_expires_at)
        )
        expires_at = result.scalar_one_or_none()
        if expires_at is None:
            return None
        return CardImageClaimDTO(
            image_id=claim.image_id,
            card_id=claim.card_id,
            original_storage_key=claim.original_storage_key,
            original_sha256=claim.original_sha256,
            original_metadata=claim.original_metadata,
            attempts=claim.attempts,
            generation=claim.generation,
            lease_token=claim.lease_token,
            lease_expires_at=expires_at,
        )

    async def complete(
        self,
        claim: CardImageClaimDTO,
        thumbnail_storage_key: str,
        thumbnail_metadata: CardThumbnailMetadata,
    ) -> CardCreatedEventDTO | None:
        now = func.now()
        result = await self.session.execute(
            update(CardImageModel)
            .where(
                CardImageModel.id == claim.image_id,
                CardImageModel.state == CardImageState.PROCESSING.value,
                CardImageModel.lease_token == claim.lease_token,
                CardImageModel.generation == claim.generation,
                CardImageModel.lease_expires_at > now,
            )
            .values(
                state=CardImageState.READY.value,
                thumbnail_storage_key=thumbnail_storage_key,
                thumbnail_format=thumbnail_metadata.image_format.value,
                thumbnail_byte_size=thumbnail_metadata.byte_size,
                thumbnail_width=thumbnail_metadata.width,
                thumbnail_height=thumbnail_metadata.height,
                lease_token=None,
                lease_expires_at=None,
                next_attempt_at=None,
                sanitized_error=None,
                updated_at=now,
            )
            .returning(CardImageModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        version = await self._increment_card_version(claim.card_id)
        card_model = await self._get_card_model(claim.card_id)
        if card_model is None:
            raise RuntimeError("La carta asociada a la imagen ya no existe.")
        event = self._make_event(card_model, version, "CardImageStateChanged")
        self.session.add(self._outbox_model(event))
        await self.session.flush()
        return event

    async def record_failure(
        self, claim: CardImageClaimDTO, sanitized_error: str
    ) -> CardCreatedEventDTO | None:
        now = func.now()
        next_state = CardImageState.FAILED if claim.attempts >= 5 else CardImageState.RETRY_PENDING
        delay = self.RETRY_DELAYS.get(claim.attempts)
        next_attempt = now + text(f"interval '{delay} seconds'") if delay else None
        result = await self.session.execute(
            update(CardImageModel)
            .where(
                CardImageModel.id == claim.image_id,
                CardImageModel.state == CardImageState.PROCESSING.value,
                CardImageModel.lease_token == claim.lease_token,
                CardImageModel.generation == claim.generation,
                CardImageModel.lease_expires_at > now,
            )
            .values(
                state=next_state.value,
                lease_token=None,
                lease_expires_at=None,
                next_attempt_at=next_attempt,
                sanitized_error=sanitized_error[:500],
                updated_at=now,
            )
            .returning(CardImageModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        version = await self._increment_card_version(claim.card_id)
        card_model = await self._get_card_model(claim.card_id)
        if card_model is None:
            raise RuntimeError("La carta asociada a la imagen ya no existe.")
        event = self._make_event(card_model, version, "CardImageStateChanged")
        self.session.add(self._outbox_model(event))
        await self.session.flush()
        return event

    async def get_card_image_status(self, card_id: str) -> CardImageStatusDTO | None:
        model = await self._get_card_model(card_id)
        if model is None:
            return None
        image = model.image
        payload = self._projection_payload(model)
        ability_payload = payload["ability"]
        if not isinstance(ability_payload, dict):
            raise ValueError("La proyección de habilidad tiene un formato inválido.")
        ready = image is not None and image.state == CardImageState.READY.value
        return CardImageStatusDTO(
            id=card_id,
            code=model.code,
            name=model.name,
            cost=model.cost,
            power=model.power,
            card_type=model.card_type,
            rarity=model.rarity,
            ability=ability_payload,
            image_status=image.state if image is not None else None,
            image_url=image.original_storage_key if ready and image is not None else None,
            thumbnail_url=image.thumbnail_storage_key if ready and image is not None else None,
            available_to_players=ready,
            status_url=f"/api/v1/content/cards/{card_id}/image-status",
            attempts=image.attempts if image is not None else 0,
            last_error=image.sanitized_error if image is not None else None,
            version=model.version,
        )

    async def requeue_failed(self, card_id: str) -> bool:
        model = await self._get_card_model(card_id, for_update=True)
        if model is None or model.image is None or model.image.state != CardImageState.FAILED.value:
            return False
        model.image.state = CardImageState.PENDING.value
        model.image.attempts = 0
        model.image.generation += 1
        model.image.lease_token = None
        model.image.lease_expires_at = None
        model.image.next_attempt_at = None
        model.image.sanitized_error = None
        model.image.updated_at = datetime.now(UTC)
        version = await self._increment_card_version(card_id)
        refreshed = await self._get_card_model(card_id)
        if refreshed is None:
            raise RuntimeError("La carta asociada a la imagen ya no existe.")
        event = self._make_event(refreshed, version, "CardImageStateChanged")
        self.session.add(self._outbox_model(event))
        await self.session.flush()
        return True

    async def referenced_storage_keys(self, keys: list[str]) -> set[str]:
        if not keys:
            return set()
        result = await self.session.execute(
            select(CardImageModel.original_storage_key, CardImageModel.thumbnail_storage_key).where(
                CardImageModel.original_storage_key.in_(keys)
                | CardImageModel.thumbnail_storage_key.in_(keys)
            )
        )
        references: set[str] = set()
        for original_key, thumbnail_key in result.all():
            references.add(original_key)
            if thumbnail_key is not None:
                references.add(thumbnail_key)
        return references

    @staticmethod
    def _claim_dto(model: CardImageModel, card_id: str) -> CardImageClaimDTO:
        return CardImageClaimDTO(
            image_id=model.id,
            card_id=card_id,
            original_storage_key=model.original_storage_key,
            original_sha256=model.original_sha256,
            original_metadata=CardImageMetadata(
                image_format=CardImageFormat(model.image_format),
                byte_size=model.byte_size,
                width=model.width,
                height=model.height,
            ),
            attempts=model.attempts,
            generation=model.generation,
            lease_token=model.lease_token or "",
            lease_expires_at=model.lease_expires_at or datetime.now(UTC),
        )

    async def _increment_card_version(self, card_id: str) -> int:
        result = await self.session.execute(
            update(CardModel)
            .where(CardModel.id == card_id)
            .values(version=CardModel.version + 1)
            .returning(CardModel.version)
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise RuntimeError("No se pudo incrementar la versión de la carta.")
        return version

    async def _get_card_model(self, card_id: str, for_update: bool = False) -> CardModel | None:
        statement = (
            select(CardModel)
            .options(joinedload(CardModel.ability), joinedload(CardModel.image))
            .where(CardModel.id == card_id)
        )
        if for_update:
            statement = statement.with_for_update(of=CardModel)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    def _projection_payload(model: CardModel) -> dict[str, JsonValue]:
        image = model.image
        ready = image is not None and image.state == CardImageState.READY.value
        ability: dict[str, JsonValue] = {
            "code": model.ability.code,
            "name": model.ability.name,
            "trigger": model.ability.ability_type if model.ability.has_effect else None,
            "effect": model.ability.description if model.ability.has_effect else None,
            "affected_card_type": None,
            "parameters": dict(model.ability.params),
        }
        return {
            "id": model.id,
            "code": model.code,
            "name": model.name,
            "cost": model.cost,
            "power": model.power,
            "card_type": model.card_type,
            "rarity": model.rarity,
            "ability": ability,
            "image_status": image.state if image is not None else None,
            "image_url": image.original_storage_key if ready and image is not None else None,
            "thumbnail_url": image.thumbnail_storage_key if ready and image is not None else None,
            "available_to_players": ready,
            "status_url": f"/api/v1/content/cards/{model.id}/image-status",
        }

    @classmethod
    def _make_event(cls, model: CardModel, version: int, event_type: str) -> CardCreatedEventDTO:
        event_id = str(uuid.uuid4())
        return CardCreatedEventDTO(
            event_id=event_id,
            aggregate_id=model.id,
            aggregate_version=version,
            correlation_id=event_id,
            payload=cls._projection_payload(model),
            event_type=event_type,
        )

    @staticmethod
    def _outbox_model(event: CardCreatedEventDTO) -> OutboxModel:
        return OutboxModel(
            id=event.event_id,
            event_type=event.event_type,
            payload={
                "event_id": event.event_id,
                "aggregate_id": event.aggregate_id,
                "aggregate_version": event.aggregate_version,
                "schema_version": 1,
                "correlation_id": event.correlation_id,
                "payload": event.payload,
            },
            status="PENDING",
            aggregate_type="card",
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            schema_version=1,
            correlation_id=event.correlation_id,
        )

    @staticmethod
    def _to_dto(model: CardImageModel) -> CardImageRecordDTO:
        original = CardImageMetadata(
            image_format=CardImageFormat(model.image_format),
            byte_size=model.byte_size,
            width=model.width,
            height=model.height,
        )
        thumbnail = None
        if model.thumbnail_format is not None:
            if (
                model.thumbnail_byte_size is None
                or model.thumbnail_width is None
                or model.thumbnail_height is None
            ):
                raise ValueError("La miniatura persistida tiene metadatos incompletos.")
            thumbnail = CardThumbnailMetadata(
                image_format=CardImageFormat(model.thumbnail_format),
                byte_size=model.thumbnail_byte_size,
                width=model.thumbnail_width,
                height=model.thumbnail_height,
            )
        return CardImageRecordDTO(
            id=model.id,
            original_storage_key=model.original_storage_key,
            original_sha256=model.original_sha256,
            original_metadata=original,
            state=CardImageState(model.state),
            thumbnail_storage_key=model.thumbnail_storage_key,
            thumbnail_metadata=thumbnail,
            attempts=model.attempts,
            generation=model.generation,
            lease_token=model.lease_token,
            lease_expires_at=model.lease_expires_at,
            next_attempt_at=model.next_attempt_at,
            sanitized_error=model.sanitized_error,
        )
