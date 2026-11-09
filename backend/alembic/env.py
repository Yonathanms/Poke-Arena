"""Ejecuta la cadena histórica con rol separado y autorización explícita.

No importa modelos de negocio, motores de aplicación ni MongoDB. La metadata
ORM está deliberadamente ausente: no se autoriza autogenerar revisiones todavía.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import command, context
from src.database.postgresql.destino_original import IDENTIDAD_SQL, identidad_original_valida
from src.database.postgresql.migracion_original import es_upgrade_original_controlado
from src.database.postgresql.revisiones import REVISION_TIPO_CUENTA
from src.shared.config import MigrationOptIn, MigrationSettings
from src.shared.destinos_originales import (
    ROL_MIGRADOR_ORIGINAL,
    ROL_SQL_ORIGINAL,
    impedir_originales_en_pruebas,
    postgres_protegido,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None
_ERROR_CORTE = "Use migrate_original.py para el único upgrade original autorizado"


def run_migrations_offline() -> None:
    """Rechaza SQL offline: 002 inspecciona y consulta el estado real del legado."""
    raise RuntimeError("La cadena histórica requiere conexión a una base aislada; no admite --sql")


def do_run_migrations(connection: Connection, *, original: bool = False) -> None:
    """Valida identidad/aislamiento dentro de la transacción antes de ejecutar DDL.

    Requiere rol no administrativo y comprueba el destino real antes del DDL.
    El contexto confirma al terminar; ante error revierte su transacción. Si el
    llamador suministra una transacción externa, conserva su responsabilidad.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        identity = tuple(connection.execute(IDENTIDAD_SQL).one())
        if original:
            if (
                not identidad_original_valida(identity, ROL_MIGRADOR_ORIGINAL)
                or context.get_revision_argument() != REVISION_TIPO_CUENTA
                or connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                != "008_flex_card_img_dims"
                or not connection.execute(text(
                    "SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = :role)"
                ), {"role": ROL_SQL_ORIGINAL}).scalar_one()
            ):
                raise RuntimeError("El corte original requiere 008 → 014 y el rol de aplicación")
        elif (
            not identity[0].startswith("pokearena_alembic_")
            or identity[1] == ROL_SQL_ORIGINAL
            or any(identity[3:])
        ):
            raise RuntimeError("Destino o rol fuera del aislamiento autorizado para 1B.1")
        context.run_migrations()


async def run_async_migrations(settings: MigrationSettings) -> None:
    """Abre conexión Alembic con timeout y la cierra incluso ante fallo.

    Usa la fábrica estándar de Alembic/SQLAlchemy, NullPool y configuración central;
    no reutiliza sesiones de aplicación ni persiste credenciales en alembic.ini.
    """
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
            await connection.run_sync(
                do_run_migrations, original=settings.ORIGINAL_MIGRATION_ENABLED
            )
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Usa conexión explícita de pruebas o conexión async dedicada, sin fallback a la API."""
    # Alembic expone el contexto de generación también para llamadas programáticas.
    context.configure(dialect_name="postgresql")
    migration_context = context.get_context()
    revision = migration_context.opts.get("revision_context")
    if revision is not None:
        if revision.command_args["autogenerate"]:
            raise RuntimeError("Autogenerate no autorizado: no existen mapeos ORM completos")
        if MigrationOptIn().ORIGINAL_MIGRATION_ENABLED:
            raise RuntimeError(_ERROR_CORTE)
        return

    cmd_opts = config.cmd_opts
    cmd = getattr(cmd_opts, "cmd", ())
    if (
        cmd_opts is not None and cmd and cmd[0] is command.history
        and not cmd_opts.indicate_current
        and "current" not in (cmd_opts.rev_range or "").split(":")
    ):
        if MigrationOptIn().ORIGINAL_MIGRATION_ENABLED:
            raise RuntimeError(_ERROR_CORTE)
        # revision_environment también invoca env.py para history. Sin "current",
        # su callback solo recorre el grafo y no necesita una conexión.
        migration_context.opts["fn"]((), migration_context)
        return

    connection = config.attributes.get("connection")
    if connection is not None:
        if postgres_protegido(connection.engine.url) or es_upgrade_original_controlado(config):
            raise RuntimeError("No se admite un destino protegido con conexión inyectada")
        do_run_migrations(connection)
        return

    settings = MigrationSettings()
    if settings.ORIGINAL_MIGRATION_ENABLED:
        if (
            not es_upgrade_original_controlado(config)
            or context.get_revision_argument() != REVISION_TIPO_CUENTA
        ):
            raise RuntimeError(_ERROR_CORTE)
        impedir_originales_en_pruebas()
    elif es_upgrade_original_controlado(config):
        raise RuntimeError("El upgrade original exige ORIGINAL_MIGRATION_ENABLED=true")
    asyncio.run(run_async_migrations(settings))


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
