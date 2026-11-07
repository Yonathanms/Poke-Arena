"""Configuración única del backend; rutas estables y secretos fuera del código."""

from functools import lru_cache
from pathlib import Path
from re import fullmatch
from typing import Any

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

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

    # Almacenamiento de imágenes
    UPLOAD_DIR: str = "./uploads"
    MAX_IMAGE_SIZE_MB: int = 5

    # Identidad / OAuth
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    PLATFORM_ADMIN_GOOGLE_SUBJECTS: str = ""
    IDENTITY_ACCESS_TOKEN_TTL_SECONDS: int = Field(default=900, ge=60, le=86_400)

    # CORS
    ALLOWED_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,http://localhost:80,http://localhost"
    )

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


class MigrationSettings(EnvironmentSettings):
    """Configura Alembic sin cargar URLs/clientes de aplicación o MongoDB.

    En 1B.1 solo permite bases de validación con prefijo pokearena_alembic_.
    La URL es explícita, sin fallback a DATABASE_URL; se rechaza el rol de API.
    El rol real y sus atributos también se comprueban antes del DDL en env.py.
    """

    MIGRATION_DATABASE_URL: str = Field(repr=False, exclude=True)

    @field_validator("MIGRATION_DATABASE_URL")
    @classmethod
    def validate_migration_target(cls, value: str) -> str:
        """Rechaza drivers, roles y destinos ajenos al aislamiento autorizado en 1B.1."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("Configure MIGRATION_DATABASE_URL con el driver asyncpg")
        url = make_url(value)
        if not url.username or url.username == "poke_api_user":
            raise ValueError("Alembic requiere un rol de migración separado de la API")
        if not url.database or not url.database.startswith("pokearena_alembic_"):
            raise ValueError("1B.1 solo permite bases aisladas pokearena_alembic_*")
        return value


@lru_cache
def get_settings() -> Settings:
    """Carga y cachea configuración; falla si faltan URLs válidas de aplicación."""
    return Settings()
