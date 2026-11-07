"""Cliente MongoDB compartido por event loop, sin bootstrap ni escrituras de negocio."""

import asyncio
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.shared.config import get_settings

settings = get_settings()

_clients: dict[int, AsyncIOMotorClient[Any]] = {}


def get_mongo_client() -> AsyncIOMotorClient[Any]:
    """Reutiliza cliente Motor del loop actual sin abrir conexiones alternativas.

    La conexión es diferida; ping/operaciones propagan errores de autenticación
    o disponibilidad dentro del timeout configurado. No crea colecciones/usuarios.
    """
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        loop_id = 0

    if loop_id not in _clients:
        timeout_ms = settings.DB_CONNECT_TIMEOUT_SECONDS * 1000
        _clients[loop_id] = AsyncIOMotorClient(
            settings.MONGO_URL,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            appname="pokearena-backend",
        )
    return _clients[loop_id]


def get_mongo_db() -> AsyncIOMotorDatabase[Any]:
    """Devuelve la base configurada sin crearla ni modificar sus colecciones."""
    client = get_mongo_client()
    return client[settings.MONGO_DB]


def close_mongo_connection() -> None:
    """Cierra todos los clientes y vacía el cache; permite llamadas repetidas."""
    for client in _clients.values():
        client.close()
    _clients.clear()

