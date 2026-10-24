"""Transaction boundary for durable image and outbox state transitions."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.content.application.dtos import (
    CardImageClaimDTO,
    CardImageStatusDTO,
    OutboxClaimDTO,
)
from src.modules.content.application.ports import (
    ICardImageProcessingTransactions,
    IOutboxProcessingTransactions,
)
from src.modules.content.domain.value_objects import CardThumbnailMetadata
from src.modules.content.infrastructure.repositories.sql_card_image_repository import (
    SqlCardImageRepository,
)
from src.modules.content.infrastructure.repositories.sql_outbox_repository import (
    SqlOutboxProcessingRepository,
)
from src.modules.content.infrastructure.unit_of_work import SqlUnitOfWork


class SqlCardImageProcessingTransactions(ICardImageProcessingTransactions):
    """Cada transición confirma una transacción corta antes de cualquier I/O externo."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def claim_next(self) -> CardImageClaimDTO | None:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                claim = await SqlCardImageRepository(session).claim_next()
            return claim

    async def renew_lease(self, claim: CardImageClaimDTO) -> CardImageClaimDTO | None:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                renewed = await SqlCardImageRepository(session).renew_lease(claim)
            return renewed

    async def complete(
        self,
        claim: CardImageClaimDTO,
        thumbnail_storage_key: str,
        thumbnail_metadata: CardThumbnailMetadata,
    ) -> bool:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                event = await SqlCardImageRepository(session).complete(
                    claim, thumbnail_storage_key, thumbnail_metadata
                )
            return event is not None

    async def record_failure(self, claim: CardImageClaimDTO, error: str) -> bool:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                event = await SqlCardImageRepository(session).record_failure(claim, error)
            return event is not None

    async def get_status(self, card_id: str) -> CardImageStatusDTO | None:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                result = await SqlCardImageRepository(session).get_card_image_status(card_id)
            return result

    async def requeue_failed(self, card_id: str) -> bool:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                result = await SqlCardImageRepository(session).requeue_failed(card_id)
            return result

    async def referenced_storage_keys(self, keys: list[str]) -> set[str]:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                result = await SqlCardImageRepository(session).referenced_storage_keys(keys)
            return result


class SqlOutboxProcessingTransactions(IOutboxProcessingTransactions):
    """Claims, ACKs y reintentos del outbox se confirman en transacciones independientes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def claim_next(self) -> OutboxClaimDTO | None:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                claim = await SqlOutboxProcessingRepository(session).claim_next()
            return claim

    async def acknowledge(self, claim: OutboxClaimDTO) -> bool:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                result = await SqlOutboxProcessingRepository(session).acknowledge(claim)
            return result

    async def schedule_retry(self, claim: OutboxClaimDTO, error: str) -> bool:
        async with self.session_factory() as session:
            async with SqlUnitOfWork(session):
                result = await SqlOutboxProcessingRepository(session).schedule_retry(claim, error)
            return result
