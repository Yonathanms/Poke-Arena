"""Emisión y validación de sesiones de plataforma con autorización del servidor."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from ..domain.sesion_model import (
    IdentidadEnConflicto,
    IdentidadInvalida,
    PerfilUsuario,
    Principal,
    Rol,
    SesionEmitida,
)
from ..ports.sesiones_ports import IdentidadColeccionPort, SesionesPort


def _huella(token: str) -> str:
    return sha256(token.encode()).hexdigest()


async def jugador_elegible_para_coleccion(
    almacen: IdentidadColeccionPort,
    token: str,
    *,
    admins: frozenset[str],
    admin_emails: frozenset[str],
) -> str | None:
    """Resuelve un jugador Google desde el Bearer y excluye identidades reservadas."""
    fila = await almacen.activa_bloqueada(_huella(token))
    if fila is None:
        return None
    actor, subject, rol, proveedor, email, email_verified = fila
    # PLAYER persistido implica PLAYER efectivo. La reserva por sub o correo es independiente.
    if not actor or not subject or proveedor != "GOOGLE" or rol != "PLAYER" or subject in admins:
        return None
    correo = email.strip().lower() if email else None
    if admin_emails:
        if not correo or correo in admin_emails or not email_verified:
            return None
        # El último login puede haber sustituido el correo de una identidad reservada.
        if await almacen.verifico_correo(actor, admin_emails):
            return None
    return actor


class Sesiones:
    """Emite tokens opacos y reevalúa permisos al autenticar cada solicitud."""

    def __init__(
        self,
        almacen: SesionesPort,
        admins: frozenset[str],
        ttl: int,
        admin_emails: frozenset[str] = frozenset(),
    ) -> None:
        """Recibe persistencia, allowlist de Google subjects y duración de la sesión."""
        self._almacen = almacen
        self._admins = admins
        self._admin_emails = admin_emails
        self._ttl = ttl

    def _credencial(self) -> tuple[str, datetime]:
        return token_urlsafe(32), datetime.now(UTC) + timedelta(seconds=self._ttl)

    def _tipo_google(self, subject: str, email: str | None, email_verified: bool) -> Rol:
        """Determina la categoría compatible con la credencial y política vigentes."""
        if subject in self._admins:
            return "PLATFORM_ADMIN"
        if email is not None and email in self._admin_emails:
            if email_verified is not True:
                raise IdentidadEnConflicto()
            return "PLATFORM_ADMIN"
        return "PLAYER"

    async def emitir(
        self, subject: str, email: str | None = None, *, email_verified: bool = False
    ) -> SesionEmitida:
        """Emite una sesión para un subject que ya verificó el proveedor OIDC."""
        email_clean = email.strip().lower() if email else None
        rol = self._tipo_google(subject, email_clean, email_verified)
        token, expira = self._credencial()
        actor, tipo_persistido, es_nuevo = await self._almacen.crear(
            subject, rol, _huella(token), expira, email=email_clean, email_verified=email_verified
        )
        return SesionEmitida(
            Principal(actor, tipo_persistido, email=email_clean),
            token,
            self._ttl,
            is_new_user=es_nuevo,
        )

    async def emitir_local(self, usuario: str, password: str) -> SesionEmitida:
        """Emite una sesión tras la verificación y el límite persistente de intentos."""
        token, expira = self._credencial()
        actor = await self._almacen.crear_local(usuario, password, _huella(token), expira)
        if actor is None:
            raise IdentidadInvalida()
        return SesionEmitida(
            Principal(actor, "PLATFORM_ADMIN"), token, self._ttl, is_new_user=False
        )

    async def revocar(self, token: str) -> None:
        """Revoca la credencial opaca sin almacenar su valor en claro."""
        await self._almacen.revocar(_huella(token))

    async def autenticar(self, token: str) -> Principal:
        """Resuelve el usuario SQL y valida el rol según el proveedor ya autenticado."""
        fila = await self._almacen.activa(_huella(token))
        if fila is None:
            raise IdentidadInvalida()
        actor, subject, rol, proveedor, email, email_verified = fila
        email_clean = email.strip().lower() if email else None
        autorizado: Rol = (
            "PLATFORM_ADMIN"
            if proveedor == "LOCAL"
            else self._tipo_google(subject, email_clean, email_verified)
        )
        if rol != autorizado:
            raise IdentidadEnConflicto()
        return Principal(actor, autorizado, email=email_clean)

    async def obtener_perfil(self, id_usuario: str) -> PerfilUsuario:
        """Recupera la información del jugador y su estado desde PostgreSQL."""
        perfil = await self._almacen.obtener_perfil(id_usuario)
        if perfil is None:
            raise IdentidadInvalida()
        return perfil
