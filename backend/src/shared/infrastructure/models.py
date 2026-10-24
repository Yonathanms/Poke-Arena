"""Modelos relacionales del Kernel Compartido (Idempotencia y Transactional Outbox)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class OutboxModel(Base):
    """
    Tabla Transactional Outbox (RNF-ALM-02, DA-01).
    Permite desacoplar y garantizar la entrega de eventos hacia NoSQL/colas
    sin transacciones distribuidas de dos fases (2PC).
    """

    __tablename__ = "shared_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyRecordModel(Base):
    """
    Registro de idempotencia para solicitudes HTTP de escritura (RNF-INT-01, DA-01).
    Almacena la respuesta original para reintentos por fallos de red.
    """

    __tablename__ = "shared_idempotency_records"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
