"""Puerto hexagonal de caché compartido (ADR-003). Sin dependencias de Redis ni FastAPI."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class CachePort(Protocol):
    """Contrato de acceso Cache-Aside con degradación Fail-Open."""

    async def get(self, key: str) -> str | None:
        """Obtiene el valor almacenado o None ante miss o error de disponibilidad."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Almacena un valor con TTL obligatorio en segundos."""
        ...

    async def delete(self, *keys: str) -> None:
        """Elimina una o más claves exactas."""
        ...

    async def delete_prefix(self, prefix: str) -> None:
        """Invalida todas las claves que comiencen por el prefijo indicado."""
        ...

    async def ping(self) -> bool:
        """Verifica conectividad del backend de caché sin propagar excepciones."""
        ...

    async def close(self) -> None:
        """Libera recursos asociados al adaptador."""
        ...
