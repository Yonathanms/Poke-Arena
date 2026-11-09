"""Emisión y validación de sesiones de plataforma con autorización del servidor."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from ..domain.sesion_model import (
    IdentidadInvalida,
    PerfilUsuario,
    Principal,
    Rol,
    SesionEmitida,
)
from ..ports.sesiones_ports import SesionesPort


def _huella(token: str) -> str:
    return sha256(token.encode()).hexdigest()


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

    async def emitir(self, subject: str, email: str | None = None) -> SesionEmitida:
        """Emite una sesión para un subject que ya verificó el proveedor OIDC."""
        email_clean = email.strip().lower() if email else None
        es_admin = (subject in self._admins) or (
            email_clean is not None and email_clean in self._admin_emails
        )
        rol: Rol = "PLATFORM_ADMIN" if es_admin else "PLAYER"
        token, expira = self._credencial()
        actor, es_nuevo = await self._almacen.crear(
            subject, rol, _huella(token), expira, email=email_clean
        )
        return SesionEmitida(
            Principal(actor, rol, email=email_clean),
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
        actor, subject, rol, proveedor, email = fila
        email_clean = email.strip().lower() if email else None
        es_admin = (
            proveedor == "LOCAL"
            or subject in self._admins
            or (email_clean is not None and email_clean in self._admin_emails)
        )
        efectivo: Rol = (
            "PLATFORM_ADMIN"
            if rol == "PLATFORM_ADMIN" and es_admin
            else "PLAYER"
        )
        return Principal(actor, efectivo, email=email_clean)

    async def obtener_perfil(self, id_usuario: str) -> PerfilUsuario:
        """Recupera la información del jugador y su estado desde PostgreSQL."""
        perfil = await self._almacen.obtener_perfil(id_usuario)
        if perfil is None:
            raise IdentidadInvalida()
        return perfil
