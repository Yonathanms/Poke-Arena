"""SQL adapters for transactional card idempotency and outbox records."""

import uuid
from typing import Any

from sqlalchemy import func, null, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.content.application.dtos import (
    CardCreatedEventDTO,
    IdempotencyRecordDTO,
)
from src.modules.content.application.ports import ICardCreationIdempotencyPort, IOutboxWriter
from src.shared.infrastructure.models import IdempotencyRecordModel, OutboxModel


class SqlCardCreationIdempotencyAdapter(ICardCreationIdempotencyPort):
    """All mutations use the supplied UoW session; resolution uses a fresh primary session."""

    OPERATION = "POST:/api/v1/content/cards"

    def __init__(
        self,
        session: AsyncSession,
        primary_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session = session
        self.primary_session_factory = primary_session_factory

    @staticmethod
    def _guard_key(actor_id: str, operation: str, key: str) -> str:
        return f"{actor_id}\x1f{operation}\x1f{key}"

    async def acquire_key_guard(self, actor_id: str, operation: str, key: str) -> None:
        await self.session.execute(
            select(
                func.pg_advisory_lock(
                    func.hashtextextended(self._guard_key(actor_id, operation, key), 0)
                )
            )
        )
        # El bloqueo es de sesión y sobrevive al commit de esta transacción corta.
        await self.session.commit()

    async def end_preflight_read(self) -> None:
        """Cierra la transacción de lectura antes del I/O lento de archivos."""
        if self.session.in_transaction():
            await self.session.commit()

    async def release_key_guard(self, actor_id: str, operation: str, key: str) -> None:
        await self.session.execute(
            select(
                func.pg_advisory_unlock(
                    func.hashtextextended(self._guard_key(actor_id, operation, key), 0)
                )
            )
        )
        await self.session.commit()

    async def find(self, actor_id: str, operation: str, key: str) -> IdempotencyRecordDTO | None:
        result = await self.session.execute(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.actor_id == actor_id,
                IdempotencyRecordModel.operation == operation,
                IdempotencyRecordModel.idempotency_key == key,
            )
        )
        return self._to_dto(result.scalar_one_or_none())

    async def reserve(self, actor_id: str, operation: str, key: str, request_hash: str) -> bool:
        statement = (
            insert(IdempotencyRecordModel)
            .values(
                id=str(uuid.uuid4()),
                actor_id=actor_id,
                operation=operation,
                idempotency_key=key,
                endpoint=operation,
                request_hash=request_hash,
                resource_id=None,
                response_status=None,
                response_body=null(),
            )
            .on_conflict_do_nothing(constraint="uq_shared_idempotency_scope")
            .returning(IdempotencyRecordModel.id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def complete(
        self,
        actor_id: str,
        operation: str,
        key: str,
        request_hash: str,
        resource_id: str,
        response_body: dict[str, Any],
    ) -> None:
        statement = (
            update(IdempotencyRecordModel)
            .where(
                IdempotencyRecordModel.actor_id == actor_id,
                IdempotencyRecordModel.operation == operation,
                IdempotencyRecordModel.idempotency_key == key,
                IdempotencyRecordModel.request_hash == request_hash,
                IdempotencyRecordModel.response_status.is_(None),
            )
            .values(resource_id=resource_id, response_status=201, response_body=response_body)
            .returning(IdempotencyRecordModel.id)
        )
        result = await self.session.execute(statement)
        if result.scalar_one_or_none() is None:
            raise RuntimeError("No se pudo completar la respuesta idempotente de Crear Carta.")

    async def find_on_primary(
        self, actor_id: str, operation: str, key: str
    ) -> IdempotencyRecordDTO | None:
        async with self.primary_session_factory() as session:
            result = await session.execute(
                select(IdempotencyRecordModel).where(
                    IdempotencyRecordModel.actor_id == actor_id,
                    IdempotencyRecordModel.operation == operation,
                    IdempotencyRecordModel.idempotency_key == key,
                )
            )
            return self._to_dto(result.scalar_one_or_none())

    @staticmethod
    def _to_dto(model: IdempotencyRecordModel | None) -> IdempotencyRecordDTO | None:
        if model is None:
            return None
        return IdempotencyRecordDTO(
            actor_id=model.actor_id,
            operation=model.operation,
            idempotency_key=model.idempotency_key,
            request_hash=model.request_hash,
            resource_id=model.resource_id,
            response_status=model.response_status,
            response_body=model.response_body,
        )


class SqlOutboxWriter(IOutboxWriter):
    """Appends the initial event using the same session as the card transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_card_created(self, event: CardCreatedEventDTO) -> None:
        await self.add_event(event)

    async def add_event(self, event: CardCreatedEventDTO) -> None:
        self.session.add(
            OutboxModel(
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
        )
        await self.session.flush()
