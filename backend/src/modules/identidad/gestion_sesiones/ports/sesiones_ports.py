"""Operaciones de persistencia para sesiones y verificación local."""

from datetime import datetime
from typing import Protocol

from ..domain.sesion_model import PerfilUsuario, Rol


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
    ) -> tuple[str, bool]:
        """Confirma una sesión Google y devuelve (identidad SQL, es_nuevo)."""
        ...

    async def crear_local(
        self, usuario: str, password: str, huella: str, expira: datetime
    ) -> str | None:
        """Verifica credenciales, registra intentos y emite una sesión al acertar."""
        ...

    async def activa(self, huella: str) -> tuple[str, str, str, str, str | None] | None:
        """Devuelve ID, subject, rol, proveedor y email de una sesión activa."""
        ...

    async def revocar(self, huella: str) -> None:
        """Invalida una sesión por su hash. Admite repetición."""
        ...
