"""Mapeos del catálogo en 1B.2B: persistencia, sin reglas de negocio ni DDL.

Los CHECK reflejan el esquema objetivo. Las relaciones requieren carga explícita
para evitar I/O asíncrono implícito.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.postgresql.base import Base


class HabilidadORM(Base):
    """Habilidad existente reutilizable; no implementa su creación ni sus efectos."""

    __tablename__ = "catalog_abilities"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="catalog_abilities_pkey"),
        UniqueConstraint("code", name="catalog_abilities_code_key"),
        CheckConstraint("code ~ '^HAB-[0-9]{3}$'", name="ck_catalog_abilities_code"),
        CheckConstraint(
            "(code = 'HAB-000' AND ability_type = 'HAB-000' AND has_effect = false) "
            "OR code <> 'HAB-000'", name="ck_catalog_abilities_reserved_none",
        ),
        ForeignKeyConstraint(
            ["evolution_target_card_id"], ["catalog_cards.id"],
            name="fk_catalog_abilities_evolution_target", ondelete="RESTRICT",
        ),
    )

    id: Mapped[str] = mapped_column(String(36))
    code: Mapped[str] = mapped_column(String(7))
    name: Mapped[str] = mapped_column(String(100))
    ability_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(500), server_default=text("''"))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    has_effect: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    evolution_target_card_id: Mapped[str | None] = mapped_column(String(36))
    cartas: Mapped[list["CartaORM"]] = relationship(
        back_populates="habilidad", foreign_keys="CartaORM.ability_id", lazy="raise",
        passive_deletes="all", cascade="save-update, merge",
    )
    destino_evolucion: Mapped["CartaORM | None"] = relationship(
        foreign_keys=[evolution_target_card_id], lazy="raise",
    )


class ImagenCartaORM(Base):
    """Única representación de metadatos/estado SQL; no almacena bytes ni usa GridFS."""

    __tablename__ = "catalog_card_images"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="catalog_card_images_pkey"),
        CheckConstraint(
            "state IN ('PENDING', 'PROCESSING', 'RETRY_PENDING', 'READY', 'FAILED')",
            name="ck_catalog_card_images_state",
        ),
        CheckConstraint("attempts >= 0", name="ck_catalog_card_images_attempts"),
        CheckConstraint("generation >= 0", name="ck_catalog_card_images_generation"),
        CheckConstraint(
            "original_sha256 ~ '^[0-9a-fA-F]{64}$'", name="ck_catalog_card_images_sha256",
        ),
        CheckConstraint(
            "image_format IN ('PNG', 'JPEG', 'WEBP')", name="ck_catalog_card_images_format",
        ),
        CheckConstraint(
            "thumbnail_format IS NULL OR thumbnail_format = 'WEBP'",
            name="ck_catalog_card_images_thumbnail_format",
        ),
        CheckConstraint("byte_size > 0", name="ck_catalog_card_images_byte_size"),
        CheckConstraint("byte_size <= 5000000", name="ck_catalog_card_images_byte_size_limit"),
        CheckConstraint("width > 0 AND height > 0", name="ck_catalog_card_images_dimensions"),
        CheckConstraint(
            "width >= 600 AND height >= 840 "
            "AND CAST(width AS bigint) * 7 = CAST(height AS bigint) * 5",
            name="ck_catalog_card_images_aspect",
        ),
        CheckConstraint(
            "state <> 'READY' OR (thumbnail_storage_key IS NOT NULL "
            "AND thumbnail_format IS NOT NULL AND thumbnail_byte_size IS NOT NULL "
            "AND thumbnail_byte_size > 0 AND thumbnail_width IS NOT NULL "
            "AND thumbnail_height IS NOT NULL AND thumbnail_width = 200 "
            "AND thumbnail_height = 280)",
            name="ck_catalog_card_images_ready_thumbnail",
        ),
        Index("ix_catalog_card_images_work", "state", "next_attempt_at", "lease_expires_at"),
        Index(
            "ix_catalog_card_images_claim", "state", "next_attempt_at",
            "lease_expires_at", "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36))
    original_storage_key: Mapped[str] = mapped_column(String(512))
    original_sha256: Mapped[str] = mapped_column(String(64))
    image_format: Mapped[str] = mapped_column(String(10))
    byte_size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_format: Mapped[str | None] = mapped_column(String(10))
    thumbnail_byte_size: Mapped[int | None] = mapped_column(Integer)
    thumbnail_width: Mapped[int | None] = mapped_column(Integer)
    thumbnail_height: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    generation: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sanitized_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    carta: Mapped["CartaORM | None"] = relationship(
        back_populates="imagen", lazy="raise", passive_deletes="all",
        cascade="save-update, merge",
    )


class ContadorCartaORM(Base):
    """Contador persistente con PK natural; importar el modelo no altera sus filas."""

    __tablename__ = "catalog_card_code_counters"
    __table_args__ = (
        PrimaryKeyConstraint("card_type", name="catalog_card_code_counters_pkey"),
        CheckConstraint("last_value BETWEEN 0 AND 999", name="ck_card_code_counter_range"),
        CheckConstraint(
            "card_type IN ('FUE', 'AGU', 'PLA', 'ELE', 'PSI', 'LUC')",
            name="ck_card_code_counter_type",
        ),
    )

    card_type: Mapped[str] = mapped_column(String(3))
    last_value: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class CartaORM(Base):
    """Carta SQL existente; la identidad y fechas deben ser provistas por el consumidor."""

    __tablename__ = "catalog_cards"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="catalog_cards_pkey1"),
        UniqueConstraint("code", name="catalog_cards_code_key"),
        UniqueConstraint("image_id", name="catalog_cards_image_id_key"),
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
            "AND right(code, 3)::INTEGER BETWEEN 1 AND 999", name="ck_catalog_cards_code_type",
        ),
        CheckConstraint("version >= 1", name="ck_catalog_cards_version"),
        ForeignKeyConstraint(
            ["ability_id"], ["catalog_abilities.id"],
            name="catalog_cards_ability_id_fkey", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["image_id"], ["catalog_card_images.id"],
            name="catalog_cards_image_id_fkey", ondelete="RESTRICT",
        ),
        Index("ix_catalog_cards_card_type", "card_type"),
        Index("ix_catalog_cards_rarity", "rarity"),
    )

    id: Mapped[str] = mapped_column(String(36))
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    cost: Mapped[int] = mapped_column(SmallInteger)
    power: Mapped[int] = mapped_column(SmallInteger)
    card_type: Mapped[str] = mapped_column(String(3))
    rarity: Mapped[str] = mapped_column(String(20))
    ability_id: Mapped[str] = mapped_column(String(36))
    image_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(BigInteger, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    habilidad: Mapped[HabilidadORM] = relationship(
        back_populates="cartas", foreign_keys=[ability_id], lazy="raise",
    )
    imagen: Mapped[ImagenCartaORM | None] = relationship(back_populates="carta", lazy="raise")
