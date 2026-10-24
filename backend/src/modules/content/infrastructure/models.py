"""Modelos SQL del módulo Content. No se importan desde capas internas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.infrastructure.database import Base


class AbilityModel(Base):
    """Definición de habilidad seleccionable por una carta."""

    __tablename__ = "catalog_abilities"
    __table_args__ = (
        CheckConstraint("code ~ '^HAB-[0-9]{3}$'", name="ck_catalog_abilities_code"),
        CheckConstraint(
            "(code = 'HAB-000' AND ability_type = 'HAB-000' AND has_effect = false) "
            "OR code <> 'HAB-000'",
            name="ck_catalog_abilities_reserved_none",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(7), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ability_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    has_effect: Mapped[bool] = mapped_column(nullable=False, default=True)
    evolution_target_card_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("catalog_cards.id", ondelete="RESTRICT"), nullable=True
    )


class CardImageModel(Base):
    """Registro durable de original y miniatura, separado de su procesamiento."""

    __tablename__ = "catalog_card_images"
    __table_args__ = (
        Index(
            "ix_catalog_card_images_claim",
            "state",
            "next_attempt_at",
            "lease_expires_at",
            "created_at",
        ),
        CheckConstraint(
            "state IN ('PENDING', 'PROCESSING', 'RETRY_PENDING', 'READY', 'FAILED')",
            name="ck_catalog_card_images_state",
        ),
        CheckConstraint("attempts >= 0", name="ck_catalog_card_images_attempts"),
        CheckConstraint("generation >= 0", name="ck_catalog_card_images_generation"),
        CheckConstraint(
            "original_sha256 ~ '^[0-9a-fA-F]{64}$'", name="ck_catalog_card_images_sha256"
        ),
        CheckConstraint(
            "image_format IN ('PNG', 'JPEG', 'WEBP')", name="ck_catalog_card_images_format"
        ),
        CheckConstraint(
            "thumbnail_format IS NULL OR thumbnail_format = 'WEBP'",
            name="ck_catalog_card_images_thumbnail_format",
        ),
        CheckConstraint("byte_size > 0", name="ck_catalog_card_images_byte_size"),
        CheckConstraint("byte_size <= 5000000", name="ck_catalog_card_images_byte_size_limit"),
        CheckConstraint("width > 0 AND height > 0", name="ck_catalog_card_images_dimensions"),
        CheckConstraint(
            "width >= 600 AND height >= 840 AND width * 7 = height * 5",
            name="ck_catalog_card_images_aspect",
        ),
        CheckConstraint(
            "state <> 'READY' OR (thumbnail_storage_key IS NOT NULL "
            "AND thumbnail_format IS NOT NULL AND thumbnail_byte_size > 0 "
            "AND thumbnail_width = 200 AND thumbnail_height = 280)",
            name="ck_catalog_card_images_ready_thumbnail",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    image_format: Mapped[str] = mapped_column(String(10), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    thumbnail_byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sanitized_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    card: Mapped[CardModel | None] = relationship(back_populates="image", uselist=False)


class CardCodeCounterModel(Base):
    """Contador transaccional independiente para cada tipo de carta."""

    __tablename__ = "catalog_card_code_counters"
    __table_args__ = (
        CheckConstraint("last_value BETWEEN 0 AND 999", name="ck_card_code_counter_range"),
    )

    card_type: Mapped[str] = mapped_column(String(3), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CardModel(Base):
    """Carta transaccional; los adaptadores de contenido la reconstruyen como entidad."""

    __tablename__ = "catalog_cards"
    __table_args__ = (
        CheckConstraint("cost BETWEEN 0 AND 10", name="ck_catalog_cards_cost"),
        CheckConstraint("power BETWEEN -20 AND 20", name="ck_catalog_cards_power"),
        CheckConstraint("length(btrim(name)) BETWEEN 1 AND 100", name="ck_catalog_cards_name"),
        CheckConstraint(
            "card_type IN ('FUE', 'AGU', 'PLA', 'ELE', 'PSI', 'LUC')",
            name="ck_catalog_cards_type",
        ),
        CheckConstraint(
            "rarity IN ('COMUN', 'POCO_COMUN', 'RARA', 'LEGENDARIA')",
            name="ck_catalog_cards_rarity",
        ),
        CheckConstraint(
            "code = 'PKA-' || card_type || '-' || right(code, 3) "
            "AND code ~ '^PKA-(FUE|AGU|PLA|ELE|PSI|LUC)-[0-9]{3}$' "
            "AND right(code, 3)::INTEGER BETWEEN 1 AND 999",
            name="ck_catalog_cards_code_type",
        ),
        CheckConstraint("version >= 1", name="ck_catalog_cards_version"),
        UniqueConstraint("image_id", name="uq_catalog_cards_image_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cost: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    power: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    card_type: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    rarity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_abilities.id", ondelete="RESTRICT"), nullable=False
    )
    image_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_card_images.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    ability: Mapped[AbilityModel] = relationship(foreign_keys=[ability_id])
    image: Mapped[CardImageModel] = relationship(back_populates="card")


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
