"""Adaptador de caché en memoria con TTL real y evicción LRU (ADR-003)."""

import time
from collections import OrderedDict


class InMemoryCacheAdapter:
    """Caché ligero en memoria para desarrollo local sin Redis o pruebas aisladas."""

    def __init__(self, max_entries: int = 2048) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries debe ser mayor que cero")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._errors = 0

    @property
    def metrics(self) -> dict[str, int | str]:
        """Expone métricas básicas de observabilidad del caché."""
        return {
            "backend": "memory",
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
        }

    def _purgar_expiradas(self, ahora: float) -> None:
        expiradas = [k for k, (_, expira) in self._entries.items() if expira <= ahora]
        for clave in expiradas:
            self._entries.pop(clave, None)

    async def get(self, key: str) -> str | None:
        ahora = time.monotonic()
        entrada = self._entries.get(key)
        if entrada is None:
            self._misses += 1
            return None
        valor, expira_en = entrada
        if expira_en <= ahora:
            self._entries.pop(key, None)
            self._misses += 1
            return None
        self._entries.move_to_end(key)
        self._hits += 1
        return valor

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            self._entries.pop(key, None)
            return
        ahora = time.monotonic()
        expira_en = ahora + ttl_seconds
        if key in self._entries:
            self._entries[key] = (value, expira_en)
            self._entries.move_to_end(key)
            return
        if len(self._entries) >= self._max_entries:
            self._purgar_expiradas(ahora)
        while len(self._entries) >= self._max_entries:
            self._entries.popitem(last=False)
        self._entries[key] = (value, expira_en)

    async def delete(self, *keys: str) -> None:
        for clave in keys:
            self._entries.pop(clave, None)

    async def delete_prefix(self, prefix: str) -> None:
        objetivos = [k for k in self._entries if k.startswith(prefix)]
        for clave in objetivos:
            self._entries.pop(clave, None)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._entries.clear()
