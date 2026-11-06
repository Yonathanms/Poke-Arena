import asyncio
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.shared.config import get_settings

settings = get_settings()

_clients: dict[int, AsyncIOMotorClient[Any]] = {}


def get_mongo_client() -> AsyncIOMotorClient[Any]:
    """Retorna cliente asíncrono Motor para MongoDB :27017."""
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        loop_id = 0

    if loop_id not in _clients:
        _clients[loop_id] = AsyncIOMotorClient(settings.MONGO_URL)
    return _clients[loop_id]


def get_mongo_db() -> AsyncIOMotorDatabase[Any]:
    """Retorna la base de datos de MongoDB configurada."""
    client = get_mongo_client()
    return client[settings.MONGO_DB]


def close_mongo_connection() -> None:
    """Cierra las conexiones activas con MongoDB."""
    for client in _clients.values():
        client.close()
    _clients.clear()

