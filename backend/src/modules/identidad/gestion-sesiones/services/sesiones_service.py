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

    async def emitir(self, subject: str) -> SesionEmitida:
        """Emite una sesión para un subject que ya verificó el proveedor OIDC."""
        rol: Rol = "PLATFORM_ADMIN" if subject in self._admins else "PLAYER"
        token = token_urlsafe(32)
        expira = datetime.now(UTC) + timedelta(seconds=self._ttl)
        actor = await self._almacen.crear(subject, rol, _huella(token), expira)
        return SesionEmitida(Principal(actor, rol), token, self._ttl)

    async def autenticar(self, token: str) -> Principal:
        """Resuelve el usuario SQL y exige tanto el rol vigente como la allowlist."""
        fila = await self._almacen.activa(_huella(token))
        if fila is None:
            raise IdentidadInvalida()
        actor, subject, rol = fila
        efectivo: Rol = (
            "PLATFORM_ADMIN" if rol == "PLATFORM_ADMIN" and subject in self._admins else "PLAYER"
        )
        return Principal(actor, efectivo)
