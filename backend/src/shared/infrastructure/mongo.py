import asyncio

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.shared.infrastructure.config import get_settings

settings = get_settings()

_clients: dict[int, AsyncIOMotorClient] = {}


def get_mongo_client() -> AsyncIOMotorClient:
    """Retorna la instancia del cliente asíncrono Motor para el event loop actual."""
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        loop_id = 0

    if loop_id not in _clients:
        _clients[loop_id] = AsyncIOMotorClient(settings.MONGO_URL)
    return _clients[loop_id]


def get_mongo_db() -> AsyncIOMotorDatabase:
    """Retorna la base de datos de MongoDB configurada en el loop activo."""
    client = get_mongo_client()
    return client[settings.MONGO_DB]


def close_mongo_connection() -> None:
    """Cierra las conexiones activas con MongoDB."""
    global _clients
    for client in _clients.values():
        client.close()
    _clients.clear()
