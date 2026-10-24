"""Modelos relacionales del Kernel Compartido (Idempotencia y Transactional Outbox)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class OutboxModel(Base):
    """
    Tabla Transactional Outbox (RNF-ALM-02, DA-01).
    Permite desacoplar y garantizar la entrega de eventos hacia NoSQL/colas
    sin transacciones distribuidas de dos fases (2PC).
    """

    __tablename__ = "shared_outbox"
    __table_args__ = (
        Index(
            "ix_shared_outbox_claim",
            "status",
            "next_attempt_at",
            "lease_expires_at",
            "created_at",
        ),
        UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_shared_outbox_aggregate_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aggregate_type: Mapped[str] = mapped_column(String(60), nullable=False, default="legacy")
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, default="legacy")
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sanitized_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class IdempotencyRecordModel(Base):
    """
    Registro de idempotencia para solicitudes HTTP de escritura (RNF-INT-01, DA-01).
    Almacena la respuesta original para reintentos por fallos de red.
    """

    __tablename__ = "shared_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "operation", "idempotency_key", name="uq_shared_idempotency_scope"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, default="__legacy__")
    operation: Mapped[str] = mapped_column(String(200), nullable=False, default="legacy")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
