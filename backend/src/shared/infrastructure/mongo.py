from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.shared.infrastructure.config import get_settings

settings = get_settings()

_mongo_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Retorna la instancia global del cliente asíncrono Motor para MongoDB."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(settings.MONGO_URL)
    return _mongo_client


def get_mongo_db() -> AsyncIOMotorDatabase:
    """Retorna la base de datos de MongoDB configurada."""
    client = get_mongo_client()
    return client[settings.MONGO_DB]


def close_mongo_connection() -> None:
    """Cierra la conexión activa con MongoDB al apagar la aplicación."""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
