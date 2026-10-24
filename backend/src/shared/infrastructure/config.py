from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la aplicación leída desde variables de entorno o archivo .env."""

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "Poké-Arena Backend"
    API_V1_PREFIX: str = "/api/v1"
    PORT: int = 8000

    # PostgreSQL Master (Escritura y transacciones ACID)
    DATABASE_WRITE_URL: str = (
        "postgresql+asyncpg://postgres:postgres_secure_pass_2026@localhost:5432/pokearena_db"
    )

    # PostgreSQL Réplica (Lecturas no críticas - RNF-DIS-02)
    DATABASE_READ_URL: str = (
        "postgresql+asyncpg://postgres:postgres_secure_pass_2026@localhost:5433/pokearena_db"
    )

    # MongoDB (Proyecciones de Catálogo NoSQL y Bitácora)
    MONGO_URL: str = "mongodb://mongoadmin:mongo_secure_pass_2026@localhost:27017/pokearena_catalog?authSource=admin"
    MONGO_DB: str = "pokearena_catalog"

    # Almacenamiento local de medios (imágenes)
    UPLOAD_DIR: str = "./uploads"
    MAX_IMAGE_SIZE_MB: int = 5

    # CORS
    ALLOWED_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,http://localhost:80,http://localhost"
    )

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
