"""Interfaces de los puertos de gestion-ubicaciones."""
from abc import ABC, abstractmethod


class IUbicacionRepository(ABC):
    @abstractmethod
    async def verificar_idempotencia(self, key: str) -> dict | None: ...

    @abstractmethod
    async def guardar(self, datos: dict, outbox_payload: dict, idempotency_key: str) -> dict: ...


class IProcesadorImagenUbicacion(ABC):
    @abstractmethod
    async def procesar(self, archivo_bytes: bytes, content_type: str) -> tuple[str, str]: ...
