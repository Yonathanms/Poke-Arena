"""Acceso a identidad y sesiones con transacciones explícitas."""

import asyncio
from datetime import datetime
from re import fullmatch
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.postgresql.revisiones import REVISION_IDENTIDAD_LOCAL

from ..domain.sesion_model import IdentidadLimitada, IdentidadNoDisponible, Rol
from .password_local import crear_hash, verificar_hash


async def _destino(sesion: AsyncSession, *, local: bool = False) -> None:
    """Aísla toda escritura y exige la revisión de credenciales para LOCAL."""
    base, superusuario = (
        await sesion.execute(
            text("SELECT current_database(), rolsuper FROM pg_roles WHERE rolname=current_user")
        )
    ).one()
    if not base.startswith("pokearena_alembic_") or superusuario:
        raise IdentidadNoDisponible()
    if local and await sesion.scalar(text("SELECT version_num FROM alembic_version")) != (
        REVISION_IDENTIDAD_LOCAL
    ):
        raise IdentidadNoDisponible()


async def _insertar_sesion(
    sesion: AsyncSession, usuario_id: str, huella: str, expira: datetime
) -> None:
    """Reutiliza la persistencia de sesiones para cualquier proveedor verificado."""
    await sesion.execute(
        text("""
            INSERT INTO identity_sessions (id, user_id, token_hash, expires_at)
            VALUES (:id, :usuario, :huella, :expira)
        """),
        {"id": str(uuid4()), "usuario": usuario_id, "huella": huella, "expira": expira},
    )


async def _comparar(password: str, guardado: str) -> bool:
    """Retiene el presupuesto de cómputo hasta concluir scrypt si hay cancelación."""
    calculo = asyncio.create_task(asyncio.to_thread(verificar_hash, password, guardado))
    try:
        return await asyncio.shield(calculo)
    except asyncio.CancelledError:
        await calculo
        raise


class SqlSesiones:
    """Abre sesiones oficiales y limita LOCAL a un destino explícito."""

    def __init__(self, factory: async_sessionmaker[AsyncSession], local: bool = False) -> None:
        """Recibe la fábrica compartida y el opt-in de identidad local."""
        self._factory, self._local = factory, local

    async def crear(self, subject: str, rol: Rol, huella: str, expira: datetime) -> str:
        """Reutiliza una identidad Google por proveedor y subject."""
        try:
            async with self._factory() as sesion, sesion.begin():
                await _destino(sesion)
                usuario = await sesion.execute(
                    text("""
                        INSERT INTO identity_users (id, provider, provider_subject, role)
                        VALUES (:id, 'GOOGLE', :subject, :rol)
                        ON CONFLICT (provider, provider_subject)
                        DO UPDATE SET role = EXCLUDED.role, updated_at = now()
                        RETURNING id
                    """),
                    {"id": str(uuid4()), "subject": subject, "rol": rol},
                )
                id_usuario = str(usuario.scalar_one())
                await _insertar_sesion(sesion, id_usuario, huella, expira)
            return id_usuario
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None

    async def provisionar_local(self, usuario: str, password: str) -> str:
        """Crea el único administrador local sin rotar una credencial existente."""
        if not self._local:
            raise IdentidadNoDisponible()
        if not fullmatch(r"[a-z][a-z0-9_-]{2,62}", usuario):
            raise ValueError("Identificador local inválido")
        guardado = await asyncio.to_thread(crear_hash, password)
        try:
            async with self._factory() as sesion, sesion.begin():
                await _destino(sesion, local=True)
                await sesion.execute(
                    text("""
                        INSERT INTO identity_users
                            (id, provider, provider_subject, role,
                             local_password_hash, local_failed_attempts)
                        VALUES (:id, 'LOCAL', :usuario, 'PLATFORM_ADMIN', :hash, 0)
                        ON CONFLICT DO NOTHING
                    """),
                    {"id": str(uuid4()), "usuario": usuario, "hash": guardado},
                )
                resultado = await sesion.scalar(
                    text("""
                    SELECT id FROM identity_users
                    WHERE provider='LOCAL' AND provider_subject=:usuario
                """),
                    {"usuario": usuario},
                )
                if not isinstance(resultado, str):
                    raise ValueError("El administrador local ya tiene otro identificador")
                return resultado
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None

    async def crear_local(
        self, usuario: str, password: str, huella: str, expira: datetime
    ) -> str | None:
        """Aplica un presupuesto compartido y confirma sesión solo tras verificar la clave."""
        if not self._local:
            raise IdentidadNoDisponible()
        try:
            async with self._factory() as sesion, sesion.begin():
                await _destino(sesion, local=True)
                fila = (
                    await sesion.execute(
                        text("""
                    SELECT id, provider_subject, role, local_password_hash, local_failed_attempts,
                           local_blocked_until, clock_timestamp() AS ahora
                    FROM identity_users WHERE provider='LOCAL' FOR UPDATE NOWAIT
                """)
                    )
                ).one_or_none()
                if fila is None:
                    return None
                id_usuario, subject, rol, guardado, fallos, bloqueo, ahora = fila
                if bloqueo is not None and bloqueo > ahora:
                    raise IdentidadLimitada(max(1, int((bloqueo - ahora).total_seconds()) + 1))
                valido = await _comparar(password, guardado)
                autorizado = valido and usuario == subject and rol == "PLATFORM_ADMIN"
                intentos = 0 if autorizado else (0 if bloqueo is not None else fallos) + 1
                await sesion.execute(
                    text("""
                    UPDATE identity_users SET local_failed_attempts=:intentos,
                        local_blocked_until=CASE WHEN :intentos = 5
                            THEN clock_timestamp() + interval '60 seconds' ELSE NULL END
                    WHERE id=:id
                """),
                    {"intentos": intentos, "id": id_usuario},
                )
                if not autorizado:
                    return None
                await _insertar_sesion(sesion, id_usuario, huella, expira)
                return str(id_usuario)
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) == "55P03":
                raise IdentidadLimitada(1) from None
            raise IdentidadNoDisponible() from None
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None

    async def activa(self, huella: str) -> tuple[str, str, str, str] | None:
        """Lee el rol vigente de una sesión permitida, no expirada ni revocada."""
        try:
            async with self._factory() as sesion:
                fila = (
                    await sesion.execute(
                        text("""
                    SELECT u.id, u.provider_subject, u.role, u.provider
                    FROM identity_sessions s JOIN identity_users u ON u.id = s.user_id
                    WHERE s.token_hash = :huella
                      AND (u.provider = 'GOOGLE' OR (
                          u.provider = 'LOCAL' AND :local
                          AND starts_with(current_database()::text, 'pokearena_alembic_')
                      ))
                      AND s.revoked_at IS NULL AND s.expires_at > statement_timestamp()
                """),
                        {"huella": huella, "local": self._local},
                    )
                ).one_or_none()
            return (
                None if fila is None else (str(fila[0]), str(fila[1]), str(fila[2]), str(fila[3]))
            )
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None

    async def revocar(self, huella: str) -> None:
        """Marca revocada una sesión en el destino aislado."""
        try:
            async with self._factory() as sesion, sesion.begin():
                await _destino(sesion)
                await sesion.execute(
                    text("""
                    UPDATE identity_sessions SET revoked_at=clock_timestamp()
                    WHERE token_hash=:huella AND revoked_at IS NULL
                """),
                    {"huella": huella},
                )
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None
