"""Transactional application service for creating a pending catalog card."""

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from src.modules.content.application.dtos import (
    AbilityDefinitionDTO,
    CardCreatedEventDTO,
    CardCreationSnapshot,
    CardImageRecordDTO,
    CreateCardResult,
    IdempotencyRecordDTO,
    JsonValue,
)
from src.modules.content.application.ports import (
    IAbilityRepository,
    ICardCodeAllocator,
    ICardCreationIdempotencyPort,
    ICardImageInspector,
    ICardImageRepository,
    ICardRepository,
    IImageStoragePort,
    IOutboxWriter,
)
from src.modules.content.domain.entities import Card
from src.modules.content.domain.exceptions import (
    AbilityNotFoundError,
    CardCreationCommitOutcomeUnknownError,
    IdempotencyInProgressError,
    IdempotencyKeyReusedError,
    InvalidIdempotencyKeyError,
    OriginalImageCompensationError,
)
from src.modules.content.domain.value_objects import (
    AbilityCode,
    CardImageState,
    CardRarity,
    CardType,
)
from src.shared.application.unit_of_work import IUnitOfWork

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedCardActor:
    """Actor identity supplied by the future public Identity contract."""

    actor_id: str


@dataclass(frozen=True)
class CreateCardCommand:
    name: str
    cost: int
    power: int
    card_type: CardType
    rarity: CardRarity
    ability_code: AbilityCode
    image_bytes: bytes
    actor: AuthenticatedCardActor
    idempotency_key: str
    correlation_id: str | None = None


class CreateCardUseCase:
    """Acepta una carta PENDING y publica el trabajo mediante transactional outbox."""

    OPERATION = "POST:/api/v1/content/cards"

    def __init__(
        self,
        uow: IUnitOfWork,
        card_repo: ICardRepository,
        code_allocator: ICardCodeAllocator,
        ability_repo: IAbilityRepository,
        image_repo: ICardImageRepository,
        idempotency: ICardCreationIdempotencyPort,
        outbox: IOutboxWriter,
        image_inspector: ICardImageInspector,
        file_storage: IImageStoragePort,
    ) -> None:
        self.uow = uow
        self.card_repo = card_repo
        self.code_allocator = code_allocator
        self.ability_repo = ability_repo
        self.image_repo = image_repo
        self.idempotency = idempotency
        self.outbox = outbox
        self.image_inspector = image_inspector
        self.file_storage = file_storage

    async def execute(self, cmd: CreateCardCommand) -> CreateCardResult:
        normalized_name = Card.validate_fields(cmd.name, cmd.cost, cmd.power, cmd.ability_code)
        if not 1 <= len(cmd.idempotency_key) <= 128:
            raise InvalidIdempotencyKeyError()
        image_metadata = self.image_inspector.inspect_card_image(cmd.image_bytes)
        image_hash = hashlib.sha256(cmd.image_bytes).hexdigest()
        request_hash = self._request_hash(cmd, normalized_name, image_hash)

        correlation_id = cmd.correlation_id or str(uuid.uuid4())
        image_id = str(uuid.uuid4())
        card_id = str(uuid.uuid4())
        image_url: str | None = None
        await self.idempotency.acquire_key_guard(
            cmd.actor.actor_id, self.OPERATION, cmd.idempotency_key
        )
        try:
            # Serializa por llave con un advisory lock de sesión, sin transacción abierta
            # durante el almacenamiento externo del original.
            prior = await self.idempotency.find(
                cmd.actor.actor_id, self.OPERATION, cmd.idempotency_key
            )
            if prior is not None:
                return self._replay_or_conflict(prior, request_hash)
            if cmd.ability_code != AbilityCode("HAB-000"):
                existing_ability = await self.ability_repo.get_by_code(cmd.ability_code)
                if existing_ability is None:
                    raise AbilityNotFoundError(cmd.ability_code.value)
            await self.idempotency.end_preflight_read()

            extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[
                image_metadata.image_format.value
            ]
            image_url = await self.file_storage.save_file(
                cmd.image_bytes, extension, subfolder="cards/originals"
            )
            try:
                async with self.uow:
                    owner = await self.idempotency.reserve(
                        cmd.actor.actor_id,
                        self.OPERATION,
                        cmd.idempotency_key,
                        request_hash,
                    )
                    if not owner:
                        concurrent = await self.idempotency.find(
                            cmd.actor.actor_id, self.OPERATION, cmd.idempotency_key
                        )
                        if concurrent is None:
                            raise IdempotencyInProgressError()
                        return self._replay_or_conflict(concurrent, request_hash)

                    if cmd.ability_code == AbilityCode("HAB-000"):
                        await self.ability_repo.ensure_none_ability()
                    ability = await self.ability_repo.get_by_code(cmd.ability_code)
                    if ability is None:
                        raise AbilityNotFoundError(cmd.ability_code.value)

                    image_record = CardImageRecordDTO(
                        id=image_id,
                        original_storage_key=image_url,
                        original_sha256=image_hash,
                        original_metadata=image_metadata,
                        state=CardImageState.PENDING,
                    )
                    await self.image_repo.save(image_record)

                    code = await self.code_allocator.allocate_next(cmd.card_type)
                    card = Card.create(
                        code=code.value,
                        name=normalized_name,
                        cost=cmd.cost,
                        power=cmd.power,
                        card_type=cmd.card_type,
                        rarity=cmd.rarity,
                        image_url=image_url,
                        ability=ability.ability,
                        ability_code=ability.code,
                        image_state=CardImageState.PENDING,
                        image_metadata=image_metadata,
                        card_id=card_id,
                    )
                    await self.card_repo.save(card, image_id)
                    snapshot = self._snapshot(card, ability)
                    await self.outbox.add_card_created(
                        CardCreatedEventDTO(
                            event_id=str(uuid.uuid4()),
                            aggregate_id=card.id,
                            aggregate_version=1,
                            correlation_id=correlation_id,
                            payload=snapshot.as_json(),
                        )
                    )
                    await self.idempotency.complete(
                        cmd.actor.actor_id,
                        self.OPERATION,
                        cmd.idempotency_key,
                        request_hash,
                        card.id,
                        snapshot.as_json(),
                    )
                return CreateCardResult(snapshot=snapshot)
            except Exception as exc:
                # Una conexión puede perderse luego de que el primario haya confirmado.
                try:
                    accepted = await self.idempotency.find_on_primary(
                        cmd.actor.actor_id, self.OPERATION, cmd.idempotency_key
                    )
                except Exception as resolution_error:
                    logger.error("No se pudo resolver el resultado de commit de Crear Carta")
                    raise CardCreationCommitOutcomeUnknownError() from resolution_error
                if accepted is not None:
                    if accepted.request_hash != request_hash:
                        raise IdempotencyKeyReusedError() from exc
                    return self._replay_or_conflict(accepted, request_hash)
                try:
                    await self.file_storage.delete_file(image_url)
                except Exception as compensation_error:
                    logger.error("Archivo de imagen requiere conciliación posterior")
                    raise OriginalImageCompensationError() from compensation_error
                raise
        finally:
            try:
                await self.idempotency.release_key_guard(
                    cmd.actor.actor_id, self.OPERATION, cmd.idempotency_key
                )
            except Exception:
                logger.error("No se pudo liberar el bloqueo temporal de idempotencia")

    @staticmethod
    def _request_hash(cmd: CreateCardCommand, normalized_name: str, image_hash: str) -> str:
        canonical = {
            "name": normalized_name,
            "cost": cmd.cost,
            "power": cmd.power,
            "card_type": cmd.card_type.value,
            "rarity": cmd.rarity.value,
            "ability_code": cmd.ability_code.value,
            "image_sha256": image_hash,
        }
        serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _replay_or_conflict(record: IdempotencyRecordDTO, request_hash: str) -> CreateCardResult:
        if record.request_hash != request_hash:
            raise IdempotencyKeyReusedError()
        if record.response_body is None:
            raise IdempotencyInProgressError()
        return CreateCardResult(
            snapshot=CreateCardUseCase._snapshot_from_json(record.response_body), replayed=True
        )

    @staticmethod
    def _snapshot(card: Card, ability: AbilityDefinitionDTO) -> CardCreationSnapshot:
        ability_spec = ability.ability
        ability_summary: dict[str, JsonValue] = {
            "code": ability.code.value,
            "name": ability.name,
            "trigger": ability_spec.ability_type.value if ability_spec else None,
            "effect": ability_spec.description if ability_spec else None,
            "affected_card_type": None,
            "parameters": dict(ability_spec.params) if ability_spec else {},
        }
        return CardCreationSnapshot(
            id=card.id,
            code=card.code,
            name=card.name,
            cost=card.cost,
            power=card.power,
            card_type=card.card_type.value,
            rarity=card.rarity.value,
            ability=ability_summary,
            image_status=CardImageState.PENDING.value,
            image_url=None,
            thumbnail_url=None,
            available_to_players=False,
            status_url=f"/api/v1/content/cards/{card.id}/image-status",
        )

    @staticmethod
    def _snapshot_from_json(body: Mapping[str, JsonValue]) -> CardCreationSnapshot:
        cost = body["cost"]
        power = body["power"]
        ability = body["ability"]
        if not isinstance(cost, int) or isinstance(cost, bool):
            raise ValueError("El snapshot idempotente contiene un costo inválido.")
        if not isinstance(power, int) or isinstance(power, bool):
            raise ValueError("El snapshot idempotente contiene un poder inválido.")
        if not isinstance(ability, dict):
            raise ValueError("El snapshot idempotente contiene una habilidad inválida.")
        return CardCreationSnapshot(
            id=str(body["id"]),
            code=str(body["code"]),
            name=str(body["name"]),
            cost=cost,
            power=power,
            card_type=str(body["card_type"]),
            rarity=str(body["rarity"]),
            ability=ability,
            image_status=str(body["image_status"]),
            image_url=body["image_url"] if isinstance(body["image_url"], str) else None,
            thumbnail_url=(
                body["thumbnail_url"] if isinstance(body["thumbnail_url"], str) else None
            ),
            available_to_players=bool(body["available_to_players"]),
            status_url=str(body["status_url"]),
        )
