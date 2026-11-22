"""Fábrica compartida de caché por event loop (ADR-003)."""

import asyncio

from src.shared.config import get_settings

from .in_memory_cache import InMemoryCacheAdapter
from .ports import CachePort
from .redis_cache import RedisCacheAdapter

_caches: dict[asyncio.AbstractEventLoop, CachePort] = {}


def get_cache() -> CachePort:
    """Devuelve el adaptador singleton para el event loop activo."""
    loop = asyncio.get_running_loop()
    if loop not in _caches:
        settings = get_settings()
        if settings.REDIS_URL:
            _caches[loop] = RedisCacheAdapter(
                settings.REDIS_URL,
                timeout_seconds=settings.CACHE_TIMEOUT_SECONDS,
            )
        else:
            _caches[loop] = InMemoryCacheAdapter()
    return _caches[loop]


async def close_cache() -> None:
    """Cierra el adaptador asociado al event loop actual. Admite llamadas repetidas."""
    cache = _caches.pop(asyncio.get_running_loop(), None)
    if cache is not None:
        await cache.close()


__all__ = [
    "CachePort",
    "InMemoryCacheAdapter",
    "RedisCacheAdapter",
    "close_cache",
    "get_cache",
]
