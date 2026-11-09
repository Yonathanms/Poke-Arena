"""Tipos públicos de identidad para las sesiones opacas de plataforma."""

from dataclasses import dataclass, field
from typing import Literal

Rol = Literal["PLAYER", "PLATFORM_ADMIN"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Identidad SQL estable y rol efectivo de una sesión autenticada."""

    id: str
    rol: Rol
    email: str | None = None


@dataclass(frozen=True, slots=True)
class SesionEmitida:
    """Resultado de emisión. El token en claro se entrega una sola vez."""

    principal: Principal
    token: str = field(repr=False)
    expira_en: int
    is_new_user: bool = False


@dataclass(frozen=True, slots=True)
class DatosIdentidadGoogle:
    """Identidad y metadatos verificados devueltos por el proveedor Google OIDC."""

    subject: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None


@dataclass(frozen=True, slots=True)
class PerfilUsuario:
    """Datos de la cuenta y perfil de jugador persistidos en PostgreSQL."""

    user_id: str
    email: str | None
    role: Rol
    elo: int
    cubes: int
    has_received_initial_collection: bool
    created_at: str | None = None


class IdentidadNoDisponible(Exception):
    """La identidad no se pudo verificar o persistir con seguridad."""


class IdentidadInvalida(Exception):
    """La credencial no acredita una identidad válida."""


class IdentidadLimitada(Exception):
    """Presupuesto temporal de intentos agotado o verificación simultánea."""

    def __init__(self, segundos: int) -> None:
        """Expone solo el tiempo de espera, sin identificar la cuenta."""
        super().__init__()
        self.segundos = segundos
