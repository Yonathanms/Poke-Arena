"""Cliente MongoDB compartido por event loop, sin bootstrap ni escrituras de negocio."""

import asyncio
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from src.shared.config import get_settings

_clients: dict[asyncio.AbstractEventLoop, AsyncMongoClient[dict[str, Any]]] = {}


def get_mongo_client(*, conexion_directa: bool = False) -> AsyncMongoClient[dict[str, Any]]:
    """Reutiliza un cliente PyMongo Async para el event loop que lo solicita.

    La conexión es diferida; ping/operaciones propagan errores de autenticación
    o disponibilidad dentro del timeout configurado. No crea colecciones/usuarios.
    """
    loop = asyncio.get_running_loop()
    if loop not in _clients:
        settings = get_settings()
        timeout_ms = settings.DB_CONNECT_TIMEOUT_SECONDS * 1000
        opciones: dict[str, Any] = {"directConnection": True} if conexion_directa else {}
        _clients[loop] = AsyncMongoClient(
            settings.MONGO_URL,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            timeoutMS=timeout_ms,
            appname="pokearena-backend",
            **opciones,
        )
    return _clients[loop]


def get_mongo_db(*, conexion_directa: bool = False) -> AsyncDatabase[dict[str, Any]]:
    """Devuelve la base configurada sin crearla ni modificar sus colecciones."""
    client = get_mongo_client(conexion_directa=conexion_directa)
    return client[get_settings().MONGO_DB]


async def close_mongo_connection() -> None:
    """Cierra el cliente del loop propietario. Admite llamadas repetidas."""
    client = _clients.pop(asyncio.get_running_loop(), None)
    if client is not None:
        await client.close()
