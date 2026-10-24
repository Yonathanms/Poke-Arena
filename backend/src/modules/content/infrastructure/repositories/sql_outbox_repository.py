"""Short-transaction SQL claims for the transactional outbox."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.application.dtos import OutboxClaimDTO
from src.modules.content.application.ports import IOutboxProcessingRepository
from src.shared.infrastructure.models import OutboxModel


class SqlOutboxProcessingRepository(IOutboxProcessingRepository):
    LEASE_SECONDS = 60

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_next(self) -> OutboxClaimDTO | None:
        now = func.now()
        eligible = (
            (OutboxModel.status == "PENDING")
            | ((OutboxModel.status == "RETRY_PENDING") & (OutboxModel.next_attempt_at <= now))
            | ((OutboxModel.status == "PROCESSING") & (OutboxModel.lease_expires_at <= now))
        )
        result = await self.session.execute(
            select(OutboxModel)
            .where(eligible)
            .order_by(OutboxModel.created_at, OutboxModel.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.status = "PROCESSING"
        model.attempts += 1
        model.lease_token = str(uuid.uuid4())
        model.lease_expires_at = await self.session.scalar(
            select(now + text("interval '60 seconds'"))
        )
        model.next_attempt_at = None
        model.sanitized_error = None
        await self.session.flush()
        envelope = model.payload
        payload = envelope.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        return OutboxClaimDTO(
            id=model.id,
            event_type=model.event_type,
            aggregate_id=model.aggregate_id,
            aggregate_version=model.aggregate_version,
            payload=payload,
            attempts=model.attempts,
            lease_token=model.lease_token or "",
            lease_expires_at=model.lease_expires_at or datetime.now(UTC),
        )

    async def acknowledge(self, claim: OutboxClaimDTO) -> bool:
        result = await self.session.execute(
            update(OutboxModel)
            .where(
                OutboxModel.id == claim.id,
                OutboxModel.status == "PROCESSING",
                OutboxModel.lease_token == claim.lease_token,
                OutboxModel.lease_expires_at > func.now(),
            )
            .values(
                status="PROCESSED",
                processed_at=func.now(),
                lease_token=None,
                lease_expires_at=None,
                sanitized_error=None,
            )
            .returning(OutboxModel.id)
        )
        return result.scalar_one_or_none() is not None

    async def schedule_retry(self, claim: OutboxClaimDTO, sanitized_error: str) -> bool:
        delay = min(2 ** min(claim.attempts, 8), 300)
        result = await self.session.execute(
            update(OutboxModel)
            .where(
                OutboxModel.id == claim.id,
                OutboxModel.status == "PROCESSING",
                OutboxModel.lease_token == claim.lease_token,
                OutboxModel.lease_expires_at > func.now(),
            )
            .values(
                status="RETRY_PENDING",
                next_attempt_at=func.now() + text(f"interval '{delay} seconds'"),
                lease_token=None,
                lease_expires_at=None,
                sanitized_error=sanitized_error[:500],
            )
            .returning(OutboxModel.id)
        )
        return result.scalar_one_or_none() is not None
