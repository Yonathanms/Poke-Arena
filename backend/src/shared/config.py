from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global del backend Poké-Arena."""

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "Poké-Arena API"
    API_V1_PREFIX: str = "/api/v1"
    PORT: int = 8000

    # PostgreSQL :5432 (Persistencia Relacional ACID)
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres_secure_pass_2026@localhost:5432/pokearena_db"
    )

    # MongoDB :27017 (Proyecciones de Catálogo)
    MONGO_URL: str = (
        "mongodb://mongoadmin:mongo_secure_pass_2026@localhost:27017/pokearena_catalog?authSource=admin"
    )
    MONGO_DB: str = "pokearena_catalog"

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

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_bool(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "debug"}
        return bool(value)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
