"""Operaciones de persistencia que requiere la autenticación de plataforma."""

from datetime import datetime
from typing import Protocol

from ..domain.sesion_model import Rol


class SesionesPort(Protocol):
    """Almacena hashes y consulta exclusivamente sesiones Google activas."""

    async def crear(self, subject: str, rol: Rol, huella: str, expira: datetime) -> str:
        """Confirma una sesión y devuelve la identidad SQL estable."""
        ...

    async def activa(self, huella: str) -> tuple[str, str, str] | None:
        """Obtiene ID de usuario, subject y rol persistido para la huella."""
        ...
