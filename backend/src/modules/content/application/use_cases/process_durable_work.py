"""Outbox delivery and conservative image-storage reconciliation use cases."""

import logging
from datetime import UTC, datetime, timedelta

from src.modules.content.application.dtos import CardImageStatusDTO
from src.modules.content.application.ports import (
    ICardImageProcessingTransactions,
    ICardProjectionWriter,
    IImageStoragePort,
    IOutboxProcessingTransactions,
)

logger = logging.getLogger(__name__)


class ProcessOutboxEventUseCase:
    def __init__(
        self,
        transactions: IOutboxProcessingTransactions,
        projection: ICardProjectionWriter,
    ) -> None:
        self.transactions = transactions
        self.projection = projection

    async def execute_once(self) -> bool:
        claim = await self.transactions.claim_next()
        if claim is None:
            return False
        try:
            # The projection's version predicate makes re-delivery after an uncertain
            # ACK safe and prevents an older PENDING event replacing a READY snapshot.
            await self.projection.project_versioned(claim)
        except Exception as exc:
            logger.exception("No se pudo proyectar el evento outbox %s", claim.id)
            try:
                await self.transactions.schedule_retry(
                    claim, f"{type(exc).__name__}: error al actualizar proyección"[:500]
                )
            except Exception:
                logger.exception("No se pudo programar reintento del outbox %s", claim.id)
            return True
        try:
            await self.transactions.acknowledge(claim)
        except Exception:
            # Keep the event recoverable. The next lease will project idempotently.
            logger.exception("ACK incierto del evento outbox %s", claim.id)
        return True


class GetCardImageStatusUseCase:
    def __init__(self, transactions: ICardImageProcessingTransactions) -> None:
        self.transactions = transactions

    async def execute(self, card_id: str) -> CardImageStatusDTO | None:
        return await self.transactions.get_status(card_id)


class RequeueFailedCardImageUseCase:
    def __init__(self, transactions: ICardImageProcessingTransactions) -> None:
        self.transactions = transactions

    async def execute(self, card_id: str) -> bool:
        return await self.transactions.requeue_failed(card_id)


class ReconcileImageStorageUseCase:
    """Deletes only aged objects proven unreferenced by the PostgreSQL primary."""

    MINIMUM_AGE = timedelta(hours=24)

    def __init__(
        self,
        transactions: ICardImageProcessingTransactions,
        storage: IImageStoragePort,
    ) -> None:
        self.transactions = transactions
        self.storage = storage

    async def execute_once(self) -> int:
        cutoff = datetime.now(UTC) - self.MINIMUM_AGE
        candidates = []
        for folder in ("cards/originals", "cards/thumbnails"):
            candidates.extend(await self.storage.list_files(folder, cutoff))
        if not candidates:
            return 0

        keys = [item.storage_key for item in candidates]
        # If primary access fails, propagate before deleting any file.
        referenced = await self.transactions.referenced_storage_keys(keys)
        removed = 0
        for item in candidates:
            if item.storage_key in referenced:
                continue
            try:
                await self.storage.delete_file(item.storage_key)
                removed += 1
            except FileNotFoundError:
                continue
            except Exception:
                logger.exception("No se pudo conciliar el archivo huérfano %s", item.storage_key)
        return removed
