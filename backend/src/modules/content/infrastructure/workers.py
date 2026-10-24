"""Lifecycle-managed loops for durable Content image and outbox work."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.content.application.use_cases.process_card_image import ProcessCardImageUseCase
from src.modules.content.application.use_cases.process_durable_work import (
    ProcessOutboxEventUseCase,
    ReconcileImageStorageUseCase,
)
from src.modules.content.infrastructure.repositories.mongo_card_projection import (
    MongoCardProjection,
)
from src.modules.content.infrastructure.repositories.sql_processing_transactions import (
    SqlCardImageProcessingTransactions,
    SqlOutboxProcessingTransactions,
)
from src.modules.content.infrastructure.services.pillow_image_processor import PillowImageProcessor
from src.shared.infrastructure.storage import get_file_storage

logger = logging.getLogger(__name__)


async def run_content_workers(
    session_factory: async_sessionmaker[AsyncSession],
    mongo_db: AsyncIOMotorDatabase[Any],
) -> None:
    storage = get_file_storage()
    processor = PillowImageProcessor()
    image_worker = ProcessCardImageUseCase(
        SqlCardImageProcessingTransactions(session_factory),
        storage,
        processor,
        processor,
    )
    outbox_worker = ProcessOutboxEventUseCase(
        SqlOutboxProcessingTransactions(session_factory),
        MongoCardProjection(mongo_db),
    )
    reconciler = ReconcileImageStorageUseCase(
        SqlCardImageProcessingTransactions(session_factory), storage
    )
    last_reconciliation = 0.0
    loop = asyncio.get_running_loop()

    async def run_one(name: str, operation: Callable[[], Awaitable[bool | int]]) -> bool:
        try:
            result = await operation()
            return bool(result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falló el worker durable %s", name)
            return False

    while True:
        did_work = False
        did_work |= await run_one("card-image", image_worker.execute_once)
        did_work |= await run_one("outbox", outbox_worker.execute_once)
        if loop.time() - last_reconciliation >= 6 * 60 * 60:
            await run_one("image-reconciliation", reconciler.execute_once)
            last_reconciliation = loop.time()
        if not did_work:
            await asyncio.sleep(1)
