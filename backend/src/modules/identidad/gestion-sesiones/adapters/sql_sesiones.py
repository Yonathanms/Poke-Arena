"""Acceso a las tablas de identidad existentes mediante la sesión oficial."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.sesion_model import IdentidadNoDisponible, Rol


class SqlSesiones:
    """Usa una sesión por operación y reserva las escrituras al entorno autorizado."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        """Recibe la fábrica PostgreSQL compartida."""
        self._factory = factory

    async def crear(self, subject: str, rol: Rol, huella: str, expira: datetime) -> str:
        """Reutiliza identidad por proveedor y subject y confirma una sesión nueva."""
        try:
            async with self._factory() as session, session.begin():
                base = await session.scalar(text("SELECT current_database()"))
                if not isinstance(base, str) or not base.startswith("pokearena_alembic_"):
                    raise IdentidadNoDisponible()
                usuario = await session.execute(
                    text("""
                        INSERT INTO identity_users (id, provider, provider_subject, role)
                        VALUES (:id, 'GOOGLE', :subject, :rol)
                        ON CONFLICT (provider, provider_subject)
                        DO UPDATE SET role = EXCLUDED.role, updated_at = now()
                        RETURNING id
                    """),
                    {"id": str(uuid4()), "subject": subject, "rol": rol},
                )
                user_id = str(usuario.scalar_one())
                await session.execute(
                    text("""
                        INSERT INTO identity_sessions (id, user_id, token_hash, expires_at)
                        VALUES (:id, :usuario, :huella, :expira)
                    """),
                    {"id": str(uuid4()), "usuario": user_id, "huella": huella, "expira": expira},
                )
            return user_id
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None

    async def activa(self, huella: str) -> tuple[str, str, str] | None:
        """Lee el rol vigente de una sesión Google no expirada ni revocada."""
        try:
            async with self._factory() as session:
                fila = (
                    await session.execute(
                        text("""
                        SELECT u.id, u.provider_subject, u.role
                        FROM identity_sessions s JOIN identity_users u ON u.id = s.user_id
                        WHERE s.token_hash = :huella AND u.provider = 'GOOGLE'
                          AND s.revoked_at IS NULL AND s.expires_at > statement_timestamp()
                    """),
                        {"huella": huella},
                    )
                ).one_or_none()
            return None if fila is None else (str(fila[0]), str(fila[1]), str(fila[2]))
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None
