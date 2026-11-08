"""Propietario único del mapeo SQL de idempotencia; sin política de recuperación."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.postgresql.base import Base


class IdempotencyRecordORM(Base):
    """Registro existente por actor/operación/clave; None representa SQL NULL."""

    __tablename__ = "shared_idempotency_records"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_shared_idempotency_records"),
        UniqueConstraint(
            "actor_id", "operation", "idempotency_key", name="uq_shared_idempotency_scope",
        ),
        CheckConstraint(
            "(response_status IS NULL AND response_body IS NULL) OR "
            "(response_status IS NOT NULL AND response_body IS NOT NULL)",
            name="ck_shared_idempotency_response_pair",
        ),
    )

    idempotency_key: Mapped[str] = mapped_column(String(128))
    endpoint: Mapped[str] = mapped_column(String(200))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(String(128))
    operation: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(36))
