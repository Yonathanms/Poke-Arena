from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class CardModel(Base):
    """Modelo relacional de Carta en PostgreSQL (Fuente de verdad transaccional)."""

    __tablename__ = "catalog_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    power: Mapped[int] = mapped_column(Integer, nullable=False)
    card_type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rarity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ability_spec: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class LocationModel(Base):
    """Modelo relacional de Ubicación en PostgreSQL."""

    __tablename__ = "catalog_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    effect_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
