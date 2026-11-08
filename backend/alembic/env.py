"""Ejecuta la cadena histórica con rol separado y solo sobre bases aisladas 1B.1.

No importa modelos de negocio, motores de aplicación ni MongoDB. La metadata
ORM está deliberadamente ausente: no se autoriza autogenerar revisiones todavía.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.shared.config import MigrationSettings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    """Rechaza SQL offline: 002 inspecciona y consulta el estado real del legado."""
    raise RuntimeError("La cadena histórica requiere conexión a una base aislada; no admite --sql")


def do_run_migrations(connection: Connection) -> None:
    """Valida identidad/aislamiento dentro de la transacción antes de ejecutar DDL.

    Requiere rol no administrativo distinto de la API y base pokearena_alembic_*.
    El contexto confirma al terminar; ante error revierte su transacción. Si el
    llamador suministra una transacción externa, conserva su responsabilidad.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        identity = connection.execute(
            text(
                "SELECT current_database(), current_user, rolsuper, rolcreatedb, "
                "rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
        if (
            not identity[0].startswith("pokearena_alembic_")
            or identity[1] == "poke_api_user"
            or any(identity[2:])
        ):
            raise RuntimeError("Destino o rol fuera del aislamiento autorizado para 1B.1")
        context.run_migrations()


async def run_async_migrations() -> None:
    """Abre conexión Alembic con timeout y la cierra incluso ante fallo.

    Usa la fábrica estándar de Alembic/SQLAlchemy, NullPool y configuración central;
    no reutiliza sesiones de aplicación ni persiste credenciales en alembic.ini.
    """
    settings = MigrationSettings()
    configuration = dict(config.get_section(config.config_ini_section, {}))
    # Evitar interpolación ConfigParser de contraseñas que contienen %.
    configuration["sqlalchemy.url"] = settings.MIGRATION_DATABASE_URL
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={"timeout": settings.DB_CONNECT_TIMEOUT_SECONDS},
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Usa conexión explícita de pruebas o conexión async dedicada, sin fallback a la API."""
    if getattr(config.cmd_opts, "autogenerate", False):
        raise RuntimeError("Autogenerate no autorizado: no existen mapeos ORM completos")
    connection = config.attributes.get("connection")
    if connection is not None:
        do_run_migrations(connection)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
