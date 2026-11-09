"""Autoriza únicamente el upgrade de corte con un contexto local a la ejecución."""

from contextvars import ContextVar

from alembic.config import Config

from alembic import command
from src.database.postgresql.revisiones import REVISION_TIPO_CUENTA
from src.shared.config import REPOSITORY_ROOT, MigrationSettings
from src.shared.destinos_originales import impedir_originales_en_pruebas

_config_autorizada: ContextVar[Config | None] = ContextVar(
    "config_migracion_original_autorizada", default=None,
)


def es_upgrade_original_controlado(config: Config) -> bool:
    """Comprueba la identidad de la configuración creada para esta única operación."""
    return _config_autorizada.get() is config


def ejecutar_upgrade_original() -> None:
    """Valida la habilitación y llama al upgrade fijo de Alembic."""
    if not MigrationSettings().ORIGINAL_MIGRATION_ENABLED:
        raise ValueError("El upgrade original exige ORIGINAL_MIGRATION_ENABLED=true")
    impedir_originales_en_pruebas()
    config = Config(str(REPOSITORY_ROOT / "backend" / "alembic.ini"))
    token = _config_autorizada.set(config)
    try:
        command.upgrade(config, REVISION_TIPO_CUENTA)
    finally:
        _config_autorizada.reset(token)
