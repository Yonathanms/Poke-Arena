from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from src.shared.infrastructure.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Clase base declarativa de SQLAlchemy 2.0 para modelos ORM."""

    pass


pool_kwargs: dict[str, Any] = (
    {"poolclass": NullPool}
    if settings.ENVIRONMENT == "test"
    else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
)

# ------------------------------------------------------------------------------
# 1. Motor de Escritura (PostgreSQL Master - Transacciones ACID)
# ------------------------------------------------------------------------------
write_engine = create_async_engine(
    settings.DATABASE_WRITE_URL,
    echo=settings.DEBUG,
    **pool_kwargs,
)

AsyncWriteSessionLocal = async_sessionmaker(
    bind=write_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ------------------------------------------------------------------------------
# 2. Motor de Lectura (PostgreSQL Réplica - Consultas no críticas - RNF-DIS-02)
# ------------------------------------------------------------------------------
read_engine = create_async_engine(
    settings.DATABASE_READ_URL,
    echo=settings.DEBUG,
    **pool_kwargs,
)

AsyncReadSessionLocal = async_sessionmaker(
    bind=read_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ------------------------------------------------------------------------------
# Inyectores de Dependencia FastAPI (Separación de sesiones - Regla 5)
# ------------------------------------------------------------------------------
async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    """Provee una sesión con el nodo maestro SQL para operaciones de escritura."""
    async with AsyncWriteSessionLocal() as session:
        yield session


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Provee una sesión con la réplica SQL para operaciones de lectura."""
    async with AsyncReadSessionLocal() as session:
        yield session
