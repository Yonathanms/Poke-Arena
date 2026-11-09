"""Operaciones de persistencia para sesiones y verificación local."""

from datetime import datetime
from typing import Protocol

from ..domain.sesion_model import PerfilUsuario, Rol

SesionActiva = tuple[str, str, str, str, str | None, bool]


class IdentidadColeccionPort(Protocol):
    """Consulta la identidad y su evidencia en la transacción de provisión."""

    async def activa_bloqueada(self, huella: str) -> SesionActiva | None:
        """Lee la sesión Google y estabiliza sesión e identidad hasta el cierre."""
        ...

    async def verifico_correo(
        self, usuario_id: str, correos_reservados: frozenset[str]
    ) -> bool:
        """Identifica evidencia histórica de un correo reservado."""
        ...


class SesionesPort(Protocol):
    """Persiste sesiones opacas y valida sus identidades actuales."""

    async def obtener_perfil(self, id_usuario: str) -> PerfilUsuario | None:
        """Devuelve la información de la cuenta y estadísticas del jugador en SQL."""
        ...

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
        """Confirma una sesión compatible y devuelve ID, tipo persistido y alta."""
        ...

    async def crear_local(
        self, usuario: str, password: str, huella: str, expira: datetime
    ) -> str | None:
        """Verifica credenciales, registra intentos y emite una sesión al acertar."""
        ...

    async def activa(self, huella: str) -> SesionActiva | None:
        """Devuelve identidad, rol, proveedor, correo y evidencia de esa sesión."""
        ...

    async def revocar(self, huella: str) -> None:
        """Invalida una sesión por su hash. Admite repetición."""
        ...
