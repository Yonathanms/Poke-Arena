"""Operaciones de persistencia para sesiones y verificación local."""

from datetime import datetime
from typing import Protocol

from ..domain.sesion_model import Rol


class SesionesPort(Protocol):
    """Persiste sesiones opacas y valida sus identidades actuales."""

    async def crear(self, subject: str, rol: Rol, huella: str, expira: datetime) -> str:
        """Confirma una sesión Google y devuelve la identidad SQL estable."""
        ...

    async def crear_local(
        self, usuario: str, password: str, huella: str, expira: datetime
    ) -> str | None:
        """Verifica credenciales, registra intentos y emite una sesión al acertar."""
        ...

    async def activa(self, huella: str) -> tuple[str, str, str, str] | None:
        """Devuelve ID, subject, rol y proveedor de una sesión activa."""
        ...

    async def revocar(self, huella: str) -> None:
        """Invalida una sesión por su hash. Admite repetición."""
        ...
