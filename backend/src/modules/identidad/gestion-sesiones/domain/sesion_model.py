"""Tipos públicos de identidad para las sesiones opacas de plataforma."""

from dataclasses import dataclass, field
from typing import Literal

Rol = Literal["PLAYER", "PLATFORM_ADMIN"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Identidad SQL estable y rol efectivo de una sesión autenticada."""

    id: str
    rol: Rol


@dataclass(frozen=True, slots=True)
class SesionEmitida:
    """Resultado de emisión. El token en claro se entrega una sola vez."""

    principal: Principal
    token: str = field(repr=False)
    expira_en: int


class IdentidadNoDisponible(Exception):
    """La identidad no se pudo verificar o persistir con seguridad."""


class IdentidadInvalida(Exception):
    """La credencial no acredita una identidad válida."""
