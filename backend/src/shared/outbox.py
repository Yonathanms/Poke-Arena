"""Propietario único del mapeo Outbox; no ejecuta publicación ni workers."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.postgresql.base import Base


class OutboxEventORM(Base):
    """Sobre durable existente, sin defaults ni restricciones de estado inventadas."""

    __tablename__ = "shared_outbox"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="shared_outbox_pkey"),
        UniqueConstraint(
            "aggregate_type", "aggregate_id", "aggregate_version",
            name="uq_shared_outbox_aggregate_version",
        ),
        CheckConstraint("attempts >= 0", name="ck_shared_outbox_attempts"),
        Index("ix_shared_outbox_event_type", "event_type"),
        Index("ix_shared_outbox_status", "status"),
        Index(
            "ix_shared_outbox_claim", "status", "next_attempt_at",
            "lease_expires_at", "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36))
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aggregate_type: Mapped[str] = mapped_column(String(60))
    aggregate_id: Mapped[str] = mapped_column(String(36))
    aggregate_version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer)
    correlation_id: Mapped[str | None] = mapped_column(String(36))
    attempts: Mapped[int] = mapped_column(Integer)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sanitized_error: Mapped[str | None] = mapped_column(String(500))
