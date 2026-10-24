"""Recoverable image processing outside long-running SQL transactions."""

import asyncio
import hashlib
import logging

from src.modules.content.application.dtos import CardImageClaimDTO
from src.modules.content.application.ports import (
    ICardImageInspector,
    ICardImageProcessingTransactions,
    IImageProcessorPort,
    IImageStoragePort,
)
from src.modules.content.domain.exceptions import InvalidCardImageError

logger = logging.getLogger(__name__)


class ProcessCardImageUseCase:
    LEASE_RENEWAL_SECONDS = 20

    def __init__(
        self,
        transactions: ICardImageProcessingTransactions,
        storage: IImageStoragePort,
        inspector: ICardImageInspector,
        processor: IImageProcessorPort,
    ) -> None:
        self.transactions = transactions
        self.storage = storage
        self.inspector = inspector
        self.processor = processor

    async def execute_once(self) -> bool:
        claim = await self.transactions.claim_next()
        if claim is None:
            return False

        attempt_key = (
            f"/uploads/cards/thumbnails/{claim.image_id}/"
            f"{claim.generation}-{claim.lease_token}.webp"
        )
        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._renew_until_stopped(claim, stop_heartbeat, lease_lost)
        )
        thumbnail_saved = False
        try:
            original = await self.storage.read_file(claim.original_storage_key)
            if hashlib.sha256(original).hexdigest() != claim.original_sha256:
                raise InvalidCardImageError()
            actual_metadata = await asyncio.to_thread(self.inspector.inspect_card_image, original)
            if actual_metadata != claim.original_metadata:
                raise InvalidCardImageError()
            thumbnail, thumbnail_metadata = await asyncio.to_thread(
                self.processor.make_card_thumbnail, original
            )
            if lease_lost.is_set():
                return False
            await self.storage.save_file_at(thumbnail, attempt_key)
            thumbnail_saved = True
            if lease_lost.is_set():
                await self._delete_own_thumbnail(attempt_key)
                return False
            completed = await self.transactions.complete(
                claim, attempt_key, thumbnail_metadata
            )
            if not completed:
                await self._delete_unreferenced_own_thumbnail(claim.card_id, attempt_key)
            return completed
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Falló el procesamiento durable de imagen %s", claim.image_id)
            try:
                await self.transactions.record_failure(claim, self._sanitize_error(exc))
            except Exception:
                # El lease expirará y el trabajo podrá reclamarse tras reiniciar el worker.
                logger.exception("No se pudo registrar el fallo de imagen %s", claim.image_id)
            if thumbnail_saved:
                await self._delete_unreferenced_own_thumbnail(claim.card_id, attempt_key)
            return True
        finally:
            stop_heartbeat.set()
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass

    async def _renew_until_stopped(
        self,
        claim: CardImageClaimDTO,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        # claim is typed as its DTO by the caller; avoid concurrent file work inside SQL.
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.LEASE_RENEWAL_SECONDS)
                return
            except TimeoutError:
                pass
            try:
                renewed = await self.transactions.renew_lease(claim)
            except Exception:
                logger.exception("No se pudo renovar el lease de imagen %s", claim.image_id)
                lease_lost.set()
                return
            if renewed is None:
                lease_lost.set()
                return

    async def _delete_unreferenced_own_thumbnail(self, card_id: str, key: str) -> None:
        try:
            status = await self.transactions.get_status(card_id)
        except Exception:
            # A failed primary read is not evidence that the object is unreferenced.
            logger.exception("No se pudo comprobar la referencia de miniatura %s", key)
            return
        if status is None or status.thumbnail_url != key:
            await self._delete_own_thumbnail(key)

    async def _delete_own_thumbnail(self, key: str) -> None:
        try:
            await self.storage.delete_file(key)
        except Exception:
            logger.exception("Miniatura de intento requiere conciliación: %s", key)

    @staticmethod
    def _sanitize_error(error: Exception) -> str:
        # Avoid persisting paths, image bytes, driver messages, or request data.
        return f"{type(error).__name__}: procesamiento de imagen fallido"[:500]
