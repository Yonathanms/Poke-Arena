"""Puertos abstractos del Kernel Compartido."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class StoredObjectDTO:
    """Minimal metadata for a generic object stored by a shared adapter."""

    storage_key: str
    modified_at: datetime


class IFileStoragePort(Protocol):
    async def save_file(self, content: bytes, extension: str, subfolder: str = "") -> str: ...

    async def save_file_at(self, content: bytes, storage_key: str) -> str: ...

    async def read_file(self, storage_key: str) -> bytes: ...

    async def delete_file(self, storage_key: str) -> None: ...

    async def list_files(
        self, subfolder: str, modified_before: datetime
    ) -> list[StoredObjectDTO]: ...


class IIdempotencyService(Protocol):
    """Puerto de aplicación para el manejo de idempotencia en solicitudes HTTP."""

    async def get_recorded_response(
        self, idempotency_key: str, endpoint: str
    ) -> dict[str, Any] | None:
        """Retorna la respuesta almacenada si la llave ya fue procesada."""
        ...

    async def record_response(
        self,
        idempotency_key: str,
        endpoint: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None:
        """Almacena la respuesta generada para solicitudes idénticas futuras."""
        ...
