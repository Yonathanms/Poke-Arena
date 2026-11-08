"""Emisión y validación de sesiones de plataforma con autorización del servidor."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from ..domain.sesion_model import IdentidadInvalida, Principal, Rol, SesionEmitida
from ..ports.sesiones_ports import SesionesPort


def _huella(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class Sesiones:
    """Emite tokens opacos y reevalúa permisos al autenticar cada solicitud."""

    def __init__(self, almacen: SesionesPort, admins: frozenset[str], ttl: int) -> None:
        """Recibe persistencia, allowlist de Google subjects y duración de la sesión."""
        self._almacen, self._admins, self._ttl = almacen, admins, ttl

    def _credencial(self) -> tuple[str, datetime]:
        return token_urlsafe(32), datetime.now(UTC) + timedelta(seconds=self._ttl)

    async def emitir(self, subject: str) -> SesionEmitida:
        """Emite una sesión para un subject que ya verificó el proveedor OIDC."""
        rol: Rol = "PLATFORM_ADMIN" if subject in self._admins else "PLAYER"
        token, expira = self._credencial()
        actor = await self._almacen.crear(subject, rol, _huella(token), expira)
        return SesionEmitida(Principal(actor, rol), token, self._ttl)

    async def emitir_local(self, usuario: str, password: str) -> SesionEmitida:
        """Emite una sesión tras la verificación y el límite persistente de intentos."""
        token, expira = self._credencial()
        actor = await self._almacen.crear_local(usuario, password, _huella(token), expira)
        if actor is None:
            raise IdentidadInvalida()
        return SesionEmitida(Principal(actor, "PLATFORM_ADMIN"), token, self._ttl)

    async def revocar(self, token: str) -> None:
        """Revoca la credencial opaca sin almacenar su valor en claro."""
        await self._almacen.revocar(_huella(token))

    async def autenticar(self, token: str) -> Principal:
        """Resuelve el usuario SQL y valida el rol según el proveedor ya autenticado."""
        fila = await self._almacen.activa(_huella(token))
        if fila is None:
            raise IdentidadInvalida()
        actor, subject, rol, proveedor = fila
        efectivo: Rol = (
            "PLATFORM_ADMIN"
            if rol == "PLATFORM_ADMIN" and (proveedor == "LOCAL" or subject in self._admins)
            else "PLAYER"
        )
        return Principal(actor, efectivo)
