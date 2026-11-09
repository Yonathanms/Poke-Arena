"""Configuración única del backend; rutas estables y secretos fuera del código."""

from functools import lru_cache
from pathlib import Path
from re import fullmatch
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from src.shared.destinos_originales import (
    PG_ORIGINAL,
    ROL_MIGRADOR_ORIGINAL,
    ROL_SQL_ORIGINAL,
    ProcesoOriginal,
    impedir_originales_en_pruebas,
    postgres_protegido,
    validar_acceso_original,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class EnvironmentSettings(BaseSettings):
    """Comparte ubicación de .env, protección de errores y timeout sin abrir clientes."""

    DB_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=60)

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
        hide_input_in_errors=True,
    )


class Settings(EnvironmentSettings):
    """Lee el .env de raíz con prioridad para variables del proceso.

    Las URLs son obligatorias: no se usan credenciales administrativas por defecto.
    Una URL ausente/inválida produce ValidationError sin mostrar su contenido.
    Las rutas relativas de archivos se interpretan respecto de la raíz del repo.
    """

    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    APP_NAME: str = "Poké-Arena API"
    API_V1_PREFIX: str = "/api/v1"
    PORT: int = 8000

    # Conservar str por compatibilidad con Alembic; excluir de repr/serialización.
    DATABASE_URL: str = Field(repr=False, exclude=True)
    MONGO_URL: str = Field(repr=False, exclude=True)
    MONGO_DB: str = "pokearena_catalog"
    MONGO_GRIDFS_BUCKET: str = "card_assets"

    OUTBOX_BATCH_SIZE: int = Field(default=20, ge=1, le=500)
    OUTBOX_CONCURRENCY: int = Field(default=4, ge=1, le=20)
    OUTBOX_POLL_SECONDS: float = Field(default=5, ge=0.1, le=300)
    OUTBOX_LEASE_SECONDS: int = Field(default=60, ge=1, le=3600)
    OUTBOX_MAX_ATTEMPTS: int = Field(default=8, ge=1, le=25)
    OUTBOX_RETRY_MAX_SECONDS: int = Field(default=300, ge=1, le=3600)

    # Almacenamiento de imágenes
    UPLOAD_DIR: str = "./uploads"
    MAX_IMAGE_SIZE_MB: int = 5

    # Identidad / OAuth
    IDENTITY_LOCAL_ENABLED: bool = False
    ORIGINAL_RUNTIME: Literal["disabled", "api", "outbox"] = "disabled"
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    PLATFORM_ADMIN_GOOGLE_SUBJECTS: str = ""
    PLATFORM_ADMIN_EMAILS: str = ""
    IDENTITY_ACCESS_TOKEN_TTL_SECONDS: int = Field(default=900, ge=60, le=86_400)

    # CORS
    ALLOWED_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,http://localhost:80,http://localhost"
    )

    @model_validator(mode="after")
    def validate_local_identity(self) -> "Settings":
        """El login local requiere opt-in y una base de validación en loopback."""
        if self.IDENTITY_LOCAL_ENABLED:
            sql = urlsplit(self.DATABASE_URL)
            if (
                self.ENVIRONMENT not in {"development", "test"}
                or sql.hostname not in {"127.0.0.1", "localhost", "::1"}
                or not sql.path.startswith("/pokearena_alembic_")
                or sql.query
            ):
                raise ValueError("La identidad local requiere un destino PostgreSQL aislado")
        return self

    @field_validator("MONGO_GRIDFS_BUCKET")
    @classmethod
    def validate_gridfs_bucket(cls, value: str) -> str:
        """Acota el nombre que forma las colecciones internas del bucket."""
        if not fullmatch(r"[a-z][a-z0-9_]{0,47}", value):
            raise ValueError("Nombre de bucket GridFS inválido")
        return value

    @field_validator("DATABASE_URL", "MONGO_URL")
    @classmethod
    def validate_database_url(cls, value: str, info: ValidationInfo) -> str:
        """Rechaza URLs vacías o de otro driver sin incluir secretos en el error."""
        schemes = (
            ("postgresql+asyncpg://",)
            if info.field_name == "DATABASE_URL"
            else ("mongodb://", "mongodb+srv://")
        )
        if not value.startswith(schemes):
            raise ValueError("Configure una URL no vacía para el driver de base de datos esperado")
        return value

    @field_validator("UPLOAD_DIR")
    @classmethod
    def resolve_upload_dir(cls, value: str) -> str:
        """Resuelve almacenamiento local desde raíz sin crear ni modificar archivos."""
        path = Path(value).expanduser()
        return str(path if path.is_absolute() else REPOSITORY_ROOT / path)

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_bool(cls, value: Any) -> bool:
        """Acepta valores booleanos de entorno conservando la convención existente."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "debug"}
        return bool(value)

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_cors(cls, value: str) -> str:
        """Exige una lista de orígenes explícitos sin comodines."""
        if "*" in value:
            raise ValueError("CORS requiere orígenes explícitos")
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Devuelve orígenes CORS normalizados sin entradas vacías."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def admin_google_subjects(self) -> frozenset[str]:
        """Devuelve subjects de Google con permisos de administrador."""
        return frozenset(
            s.strip() for s in self.PLATFORM_ADMIN_GOOGLE_SUBJECTS.split(",") if s.strip()
        )

    @property
    def admin_emails(self) -> frozenset[str]:
        """Devuelve correos normalizados con permisos de administrador."""
        return frozenset(
            e.strip().lower() for e in self.PLATFORM_ADMIN_EMAILS.split(",") if e.strip()
        )

    def verificar_destinos(self, proceso: ProcesoOriginal | None = None) -> None:
        """Valida el par configurado antes de construir clientes de aplicación."""
        if proceso is not None and self.ORIGINAL_RUNTIME not in {"disabled", proceso}:
            raise ValueError("opt_in_original_de_otro_proceso")
        try:
            sql = make_url(self.DATABASE_URL)
        except (ArgumentError, ValueError):
            raise ValueError("destino_postgresql_invalido") from None
        validar_acceso_original(
            sql, self.MONGO_URL, self.MONGO_DB,
            self.ENVIRONMENT, self.ORIGINAL_RUNTIME,
        )


class MigrationOptIn(EnvironmentSettings):
    """Lee la habilitación incluso para operaciones de Alembic sin conexión."""

    ORIGINAL_MIGRATION_ENABLED: bool = False


class MigrationSettings(MigrationOptIn):
    """Configura Alembic sin cargar URLs/clientes de aplicación o MongoDB.

    Por defecto solo admite bases aisladas con prefijo pokearena_alembic_.
    La URL es explícita, sin fallback a DATABASE_URL; se rechaza el rol de API.
    El rol real y sus atributos también se comprueban antes del DDL en env.py.
    """

    MIGRATION_DATABASE_URL: str = Field(repr=False, exclude=True)
    ENVIRONMENT: str = "development"

    @model_validator(mode="after")
    def validate_migration_target(self) -> "MigrationSettings":
        """Acepta un rol aislado o el opt-in independiente de Alembic."""
        try:
            url = make_url(self.MIGRATION_DATABASE_URL)
        except (ArgumentError, ValueError):
            raise ValueError("Configure MIGRATION_DATABASE_URL con el driver asyncpg") from None
        if url.drivername != "postgresql+asyncpg":
            raise ValueError("Configure MIGRATION_DATABASE_URL con el driver asyncpg")
        if not url.username or url.username == ROL_SQL_ORIGINAL:
            raise ValueError("Alembic requiere un rol de migración separado de la API")
        if self.ORIGINAL_MIGRATION_ENABLED:
            if (
                self.ENVIRONMENT != "development"
                or (url.host, url.port, url.database) != PG_ORIGINAL
                or url.username != ROL_MIGRADOR_ORIGINAL or not url.password or url.query
            ):
                raise ValueError("destino_original_alembic_no_autorizado")
        elif postgres_protegido(url) or not (url.database or "").startswith("pokearena_alembic_"):
            raise ValueError("1B.1 solo permite bases aisladas pokearena_alembic_*")
        return self


@lru_cache
def get_settings() -> Settings:
    """Carga y cachea configuración; falla si faltan URLs válidas de aplicación."""
    settings = Settings()
    settings.verificar_destinos()
    if settings.ORIGINAL_RUNTIME != "disabled":
        impedir_originales_en_pruebas()
    return settings
