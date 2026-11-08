"""Modelo ORM de SQLAlchemy para la tabla locations."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.postgresql.connection import Base


class UbicacionModel(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    card_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    energia_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    energia_valor: Mapped[int] = mapped_column(Integer, nullable=False)
    efecto_tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    efecto_params: Mapped[dict] = mapped_column(JSON, nullable=False)
    url_grande: Mapped[str] = mapped_column(String(500), nullable=False)
    url_tablero: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
