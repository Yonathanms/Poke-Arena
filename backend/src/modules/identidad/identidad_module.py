"""Composición de identidad y su dependencia pública para el catálogo."""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from functools import partial
from getpass import GetPassWarning, getpass
from importlib import import_module
from typing import Any
from warnings import catch_warnings, simplefilter

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.identidad.gestion_sesiones.controllers import sesiones_controller
from src.shared.config import get_settings

_PAQUETE = f"{__package__}.gestion_sesiones"
_sql = import_module(f"{_PAQUETE}.adapters.sql_sesiones")
_servicio = import_module(f"{_PAQUETE}.services.sesiones_service")
_google = import_module(f"{_PAQUETE}.adapters.google_oidc")


def crear_servicio_sesiones() -> Any:
    """Inyecta la fábrica oficial sin abrir conexiones durante la composición."""
    from src.database.postgresql.connection import AsyncSessionLocal

    ajustes = get_settings()
    admins = ajustes.admin_google_subjects
    admin_emails = ajustes.admin_emails
    return _servicio.Sesiones(
        _sql.SqlSesiones(AsyncSessionLocal, ajustes.IDENTITY_LOCAL_ENABLED),
        admins,
        ajustes.IDENTITY_ACCESS_TOKEN_TTL_SECONDS,
        admin_emails=admin_emails,
    )


def crear_autorizacion_coleccion(sesion: AsyncSession) -> Callable[[str], Awaitable[str | None]]:
    """Vincula la política central de Identidad con la transacción de Jugadores."""
    ajustes = get_settings()
    return partial(
        _servicio.jugador_elegible_para_coleccion,
        _sql.SqlIdentidadColeccion(sesion),
        admins=ajustes.admin_google_subjects,
        admin_emails=ajustes.admin_emails,
    )


requerir_administrador, requerir_jugador = sesiones_controller.crear_dependencias(
    crear_servicio_sesiones
)
Principal = _servicio.Principal
Rol = _servicio.Rol


def crear_router_identidad(provisionar: Callable[[str], Awaitable[None]]) -> APIRouter:
    """Inyecta el efecto posterior al login sin acoplar Identidad a Jugadores."""
    return sesiones_controller.crear_router(
        crear_servicio_sesiones, _google.verificar_google, requerir_jugador, provisionar
    )


async def provisionar_administrador(usuario: str, password: str) -> str:
    """Aprovisiona el administrador aislado y cierra las conexiones de la CLI."""
    from src.database.postgresql.connection import AsyncSessionLocal, engine

    try:
        engine.echo = False
        almacen = _sql.SqlSesiones(AsyncSessionLocal, get_settings().IDENTITY_LOCAL_ENABLED)
        resultado = await almacen.provisionar_local(usuario, password)
        return str(resultado)
    finally:
        await engine.dispose()


def main() -> int:
    """Solicita el secreto en terminal, sin leerlo de argumentos o entorno."""
    parser = argparse.ArgumentParser(description="Aprovisionar el administrador local aislado.")
    parser.add_argument("--usuario", required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        print("El aprovisionamiento requiere una terminal interactiva.", file=sys.stderr)
        return 1
    try:
        with catch_warnings():
            simplefilter("error", GetPassWarning)
            password = getpass("Contraseña local: ")
            confirmacion = getpass("Confirmar contraseña: ")
        if password != confirmacion:
            print("La confirmación no coincide.", file=sys.stderr)
            return 1
        usuario_id = asyncio.run(provisionar_administrador(args.usuario, password))
    except (ValueError, KeyboardInterrupt, EOFError, GetPassWarning, _sql.IdentidadNoDisponible):
        print("No se pudo aprovisionar el administrador local.", file=sys.stderr)
        return 1
    print(f"Identidad local verificada: {usuario_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
