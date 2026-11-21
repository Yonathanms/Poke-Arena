"""Interfaces de los puertos de gestion_ubicaciones."""

from abc import ABC, abstractmethod
from typing import Any


class IUbicacionRepository(ABC):
    @abstractmethod
    async def verificar_idempotencia(self, actor_id: str, key: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def guardar(
        self, actor_id: str, datos: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]: ...


class IFuenteUbicacionesSql(ABC):
    @abstractmethod
    async def listar_ubicaciones(self) -> list[dict[str, Any]]: ...


class IProyeccionUbicacionRepository(ABC):
    @abstractmethod
    async def sincronizar(self, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    async def listar_proyecciones(self) -> dict[str, dict[str, Any]]: ...


class IProcesadorImagenUbicacion(ABC):
    @abstractmethod
    async def procesar(self, archivo_bytes: bytes, content_type: str) -> tuple[str, str]: ...
