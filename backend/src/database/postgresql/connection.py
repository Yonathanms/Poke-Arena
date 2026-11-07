"""Configuración de conexión hacia la base de datos relacional PostgreSQL 16."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from src.shared.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Clase base declarativa de SQLAlchemy 2.0 para todos los modelos ORM."""

    pass


pool_kwargs: dict[str, Any] = (
    {"poolclass": NullPool}
    if settings.ENVIRONMENT == "test"
    else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
)

# Motor de conexión asíncrono hacia PostgreSQL (:5432)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    hide_parameters=True,
    connect_args={"timeout": settings.DB_CONNECT_TIMEOUT_SECONDS},
    **pool_kwargs,
)

# Fábrica de sesiones asíncronas para consultas y transacciones
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Alias para compatibilidad
write_engine = engine
AsyncWriteSessionLocal = AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provee una sesión y la cierra al terminar; el caso de uso decide el commit.

    No ejecuta DDL ni confirma transacciones automáticamente. Los errores de
    conexión/consulta se propagan al consumidor; al cerrar se revierte lo pendiente.
    """
    async with AsyncSessionLocal() as session:
        yield session


# Alias para compatibilidad
get_write_db = get_db
