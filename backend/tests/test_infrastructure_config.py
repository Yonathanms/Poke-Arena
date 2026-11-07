"""Pruebas aisladas de configuración 1A; no requieren motores ni escriben en bases."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.shared.config import REPOSITORY_ROOT, Settings


@pytest.fixture
def configured_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inyecta credenciales ficticias sin depender del .env privado del desarrollador."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://example:sql-test-secret@localhost/db")
    monkeypatch.setenv("MONGO_URL", "mongodb://example:mongo-test-secret@localhost/db")
    monkeypatch.setenv("UPLOAD_DIR", "uploads")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", "5")


def test_configuration_paths_do_not_depend_on_working_directory(
    configured_environment: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cambiar cwd no cambia el .env seleccionado ni el destino de archivos relativos."""
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.model_config["env_file"] == REPOSITORY_ROOT / ".env"
    assert Path(settings.UPLOAD_DIR) == REPOSITORY_ROOT / "uploads"


def test_process_environment_overrides_dotenv(
    configured_environment: None, tmp_path: Path
) -> None:
    """Permite credenciales de diagnóstico por proceso sin alterar secretos guardados."""
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=invalid\nMONGO_URL=invalid\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert settings.MONGO_URL.startswith("mongodb://")


def test_secrets_are_redacted(configured_environment: None) -> None:
    """Representaciones y serialización ordinaria no revelan contraseñas de conexión."""
    settings = Settings()
    rendered = repr(settings) + settings.model_dump_json()
    assert "sql-test-secret" not in rendered
    assert "mongo-test-secret" not in rendered


@pytest.mark.parametrize("field", ["DATABASE_URL", "MONGO_URL"])
def test_empty_application_urls_fail_closed(
    configured_environment: None, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """Sin URL de aplicación válida no se cae silenciosamente a un administrador."""
    monkeypatch.setenv(field, "")
    with pytest.raises(ValidationError):
        Settings()


def test_invalid_url_errors_hide_input(
    configured_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Errores de driver no reproducen una URL que contiene secretos."""
    monkeypatch.setenv("DATABASE_URL", "unsupported://user:do-not-log-this@host/db")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert "do-not-log-this" not in str(error.value)


@pytest.mark.parametrize("timeout", ["0", "61"])
def test_connection_timeout_has_operational_bounds(
    configured_environment: None, monkeypatch: pytest.MonkeyPatch, timeout: str
) -> None:
    """Evita esperas ilimitadas y límites inválidos en las conexiones oficiales."""
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", timeout)
    with pytest.raises(ValidationError):
        Settings()
