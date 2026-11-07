"""Composición de identidad y su dependencia pública para el catálogo."""

from importlib import import_module
from typing import Any

from src.shared.config import get_settings

_PAQUETE = f"{__package__}.gestion-sesiones"
_sql = import_module(f"{_PAQUETE}.adapters.sql_sesiones")
_servicio = import_module(f"{_PAQUETE}.services.sesiones_service")
_google = import_module(f"{_PAQUETE}.adapters.google_oidc")
_http = import_module(f"{_PAQUETE}.controllers.sesiones_controller")


def crear_servicio_sesiones() -> Any:
    """Inyecta la fábrica oficial sin abrir conexiones durante la composición."""
    from src.database.postgresql.connection import AsyncSessionLocal

    ajustes = get_settings()
    admins = frozenset(
        s.strip() for s in ajustes.PLATFORM_ADMIN_GOOGLE_SUBJECTS.split(",") if s.strip()
    )
    return _servicio.Sesiones(
        _sql.SqlSesiones(AsyncSessionLocal), admins, ajustes.IDENTITY_ACCESS_TOKEN_TTL_SECONDS
    )


router, requerir_administrador = _http.crear_router(
    crear_servicio_sesiones, _google.verificar_google
)
