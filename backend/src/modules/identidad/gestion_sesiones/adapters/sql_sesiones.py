"""Acceso a identidad y sesiones con transacciones explícitas."""

import asyncio
from datetime import datetime
from re import fullmatch
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.postgresql.destino_original import IDENTIDAD_SQL, destino_original_activo
from src.database.postgresql.revisiones import REVISION_TIPO_CUENTA, REVISIONES_IDENTIDAD_LOCAL
from src.shared.destinos_originales import PG_ORIGINAL

from ..domain.sesion_model import (
    IdentidadEnConflicto,
    IdentidadLimitada,
    IdentidadNoDisponible,
    PerfilUsuario,
    Rol,
)
from ..ports.sesiones_ports import SesionActiva
from .password_local import crear_hash, verificar_hash

_SESION_ACTIVA = """
    SELECT u.id, u.provider_subject, u.role, u.provider, u.email, s.id
    FROM identity_sessions s JOIN identity_users u ON u.id = s.user_id
    WHERE s.token_hash = :huella
      AND (u.provider = 'GOOGLE' OR (
          u.provider = 'LOCAL' AND :local
          AND starts_with(current_database()::text, 'pokearena_alembic_')
      ))
      AND s.revoked_at IS NULL AND s.expires_at > statement_timestamp()
"""


async def _destino(sesion: AsyncSession, *, local: bool = False) -> None:
    """Aísla toda escritura y exige la revisión de credenciales para LOCAL."""
    identidad = tuple((await sesion.execute(IDENTIDAD_SQL)).one())
    if identidad[0] == PG_ORIGINAL[2]:
        if (
            local or not destino_original_activo(identidad, "api")
            or await sesion.scalar(text("SELECT version_num FROM alembic_version"))
            != REVISION_TIPO_CUENTA
        ):
            raise IdentidadNoDisponible()
        return
    if not identidad[0].startswith("pokearena_alembic_") or identidad[3]:
        raise IdentidadNoDisponible()
    if local and await sesion.scalar(text("SELECT version_num FROM alembic_version")) not in (
        REVISIONES_IDENTIDAD_LOCAL
    ):
        raise IdentidadNoDisponible()


def _id_sesion_email_verificado(huella: str, email: str) -> UUID:
    """Vincula la evidencia del correo al ID persistido de esta sesión."""
    return uuid5(NAMESPACE_URL, f"pokearena:google-verified-email:{huella}:{email}")


def _id_sesion_admin_google(huella: str, email_verificado: str | None) -> UUID:
    """Identifica una sesión emitida para una cuenta administrativa permanente."""
    return uuid5(NAMESPACE_URL, f"pokearena:google-admin:{huella}:{email_verificado or ''}")


async def _leer_sesion_activa(
    sesion: AsyncSession, huella: str, *, local: bool, bloquear: bool = False
) -> SesionActiva | None:
    consulta = _SESION_ACTIVA + (" FOR SHARE OF u, s" if bloquear else "")
    fila = (await sesion.execute(text(consulta), {"huella": huella, "local": local})).one_or_none()
    if fila is None:
        return None
    actor, subject, rol, proveedor, email, id_sesion = fila
    admin_con_correo = (
        proveedor == "GOOGLE"
        and isinstance(email, str)
        and id_sesion == str(_id_sesion_admin_google(huella, email))
    )
    correo_verificado = (
        proveedor == "GOOGLE"
        and isinstance(email, str)
        and (admin_con_correo or id_sesion == str(_id_sesion_email_verificado(huella, email)))
    )
    if proveedor == "GOOGLE":
        sesion_admin = admin_con_correo or (
            id_sesion == str(_id_sesion_admin_google(huella, None))
        )
        # Una sesión Google histórica carece de evidencia de su categoría de emisión.
        if sesion_admin != (rol == "PLATFORM_ADMIN"):
            return None
    return str(actor), str(subject), str(rol), str(proveedor), email, correo_verificado


class SqlIdentidadColeccion:
    """Consulta elegibilidad sin abrir otra transacción ni modificar Identidad."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def activa_bloqueada(self, huella: str) -> SesionActiva | None:
        """Mantiene estable la identidad y sesión frente a login o revocación concurrente."""
        return await _leer_sesion_activa(self._sesion, huella, local=False, bloquear=True)

    async def verifico_correo(
        self, usuario_id: str, correos_reservados: frozenset[str]
    ) -> bool:
        """Contrasta la evidencia UUID5 de CI-1, incluso en sesiones expiradas o revocadas."""
        filas = await self._sesion.stream(
            text("""
                SELECT id, token_hash FROM identity_sessions
                WHERE user_id = :usuario AND substr(id, 15, 1) = '5'
            """),
            {"usuario": usuario_id},
        )
        try:
            async for id_sesion, huella in filas:
                if any(
                    id_sesion in (
                        str(_id_sesion_email_verificado(huella, correo)),
                        str(_id_sesion_admin_google(huella, correo)),
                    )
                    for correo in correos_reservados
                ):
                    return True
            return False
        finally:
            await filas.close()


async def _insertar_sesion(
    sesion: AsyncSession,
    usuario_id: str,
    huella: str,
    expira: datetime,
    *,
    email_verificado: str | None = None,
    admin_google: bool = False,
) -> None:
    """Reutiliza la persistencia de sesiones para cualquier proveedor verificado."""
    # UUID4 identifica sesiones sin evidencia, incluidas todas las históricas.
    if admin_google:
        id_sesion = _id_sesion_admin_google(huella, email_verificado)
    else:
        id_sesion = (
            _id_sesion_email_verificado(huella, email_verificado) if email_verificado else uuid4()
        )
    await sesion.execute(
        text("""
            INSERT INTO identity_sessions (id, user_id, token_hash, expires_at)
            VALUES (:id, :usuario, :huella, :expira)
        """),
        {"id": str(id_sesion), "usuario": usuario_id, "huella": huella, "expira": expira},
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

    async def crear(
        self,
        subject: str,
        rol: Rol,
        huella: str,
        expira: datetime,
        email: str | None = None,
        *,
        email_verified: bool = False,
    ) -> tuple[str, Rol, bool]:
        """Registra una categoría una vez y emite sesión solo si sigue siendo compatible."""
        try:
            async with self._factory() as sesion, sesion.begin():
                await _destino(sesion)
                parametros = {"id": str(uuid4()), "subject": subject, "email": email, "rol": rol}
                usuario = (await sesion.execute(
                    text("""
                        INSERT INTO identity_users (id, provider, provider_subject, email, role)
                        VALUES (:id, 'GOOGLE', :subject, :email, :rol)
                        ON CONFLICT (provider, provider_subject) DO NOTHING
                        RETURNING id, role
                    """),
                    parametros,
                )).one_or_none()
                es_nuevo = usuario is not None
                if usuario is None:
                    # Una sentencia nueva ve al ganador de un alta concurrente en READ COMMITTED.
                    usuario = (await sesion.execute(
                        text("""
                            UPDATE identity_users
                            SET email = COALESCE(:email, email), updated_at = now()
                            WHERE provider = 'GOOGLE' AND provider_subject = :subject
                              AND role = :rol
                            RETURNING id, role
                        """),
                        parametros,
                    )).one_or_none()
                if usuario is None:
                    raise IdentidadEnConflicto()
                id_usuario = str(usuario.id)
                tipo: Rol = "PLAYER" if usuario.role == "PLAYER" else "PLATFORM_ADMIN"

                if tipo == "PLAYER":
                    await sesion.execute(
                        text("""
                            INSERT INTO player_profiles (user_id)
                            VALUES (:user_id) ON CONFLICT (user_id) DO NOTHING
                        """),
                        {"user_id": id_usuario},
                    )

                await _insertar_sesion(
                    sesion,
                    id_usuario,
                    huella,
                    expira,
                    email_verificado=email if email_verified is True else None,
                    admin_google=tipo == "PLATFORM_ADMIN",
                )
            return id_usuario, tipo, es_nuevo
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

    async def activa(self, huella: str) -> SesionActiva | None:
        """Lee el rol vigente de una sesión permitida, no expirada ni revocada."""
        try:
            async with self._factory() as sesion:
                return await _leer_sesion_activa(sesion, huella, local=self._local)
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

    async def obtener_perfil(self, id_usuario: str) -> PerfilUsuario | None:
        """Consulta identity_users y player_profiles para verificar la conexión a SQL."""
        try:
            async with self._factory() as sesion:
                fila = (
                    await sesion.execute(
                        text("""
                            SELECT u.id, u.email, u.role,
                                   COALESCE(p.elo, 0) AS elo,
                                   COALESCE(p.cubes, 0) AS cubes,
                                   COALESCE(p.has_received_initial_collection, false) AS has_col,
                                   u.created_at::text AS created_at
                            FROM identity_users u
                            LEFT JOIN player_profiles p ON p.user_id = u.id
                            WHERE u.id = :id
                        """),
                        {"id": id_usuario},
                    )
                ).one_or_none()
                if fila is None:
                    return None
                return PerfilUsuario(
                    user_id=str(fila[0]),
                    email=fila[1] if fila[1] is None else str(fila[1]),
                    role="PLATFORM_ADMIN" if str(fila[2]) == "PLATFORM_ADMIN" else "PLAYER",
                    elo=int(fila[3]),
                    cubes=int(fila[4]),
                    has_received_initial_collection=bool(fila[5]),
                    created_at=str(fila[6]) if fila[6] is not None else None,
                )
        except SQLAlchemyError:
            raise IdentidadNoDisponible() from None
