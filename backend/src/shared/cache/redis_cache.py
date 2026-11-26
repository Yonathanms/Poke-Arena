"""Adaptador Redis distribuido con degradación estricta Fail-Open (ADR-003)."""

import asyncio
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("pokearena.cache.redis")


class RedisCacheAdapter:
    """Implementa CachePort sobre Redis Async garantizando timeout <= 150 ms y Fail-Open."""

    def __init__(
        self,
        url: str,
        timeout_seconds: float = 0.15,
        client: Redis | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._client: Redis = (
            client
            if client is not None
            else Redis.from_url(
                url,
                decode_responses=True,
                socket_timeout=timeout_seconds,
                socket_connect_timeout=timeout_seconds,
                retry_on_timeout=False,
                health_check_interval=0,
            )
        )
        self._hits = 0
        self._misses = 0
        self._errors = 0

    @property
    def metrics(self) -> dict[str, int | str]:
        """Expone métricas básicas de observabilidad del caché."""
        return {
            "backend": "redis",
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
        }

    def _registrar_fallo(self, operacion: str, exc: Exception) -> None:
        self._errors += 1
        logger.warning("cache_redis_fail_open op=%s error=%s", operacion, type(exc).__name__)

    async def get(self, key: str) -> str | None:
        try:
            valor = await asyncio.wait_for(self._client.get(key), timeout=self._timeout)
        except (RedisError, TimeoutError, OSError) as exc:
            self._registrar_fallo("get", exc)
            return None
        if valor is None:
            self._misses += 1
            return None
        self._hits += 1
        return str(valor)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            await self.delete(key)
            return
        try:
            await asyncio.wait_for(
                self._client.set(key, value, ex=ttl_seconds),
                timeout=self._timeout,
            )
        except (RedisError, TimeoutError, OSError) as exc:
            self._registrar_fallo("set", exc)

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await asyncio.wait_for(self._client.delete(*keys), timeout=self._timeout)
        except (RedisError, TimeoutError, OSError) as exc:
            self._registrar_fallo("delete", exc)

    async def delete_prefix(self, prefix: str) -> None:
        async def _escanear_y_borrar() -> None:
            lote: list[str] = []
            async for clave in self._client.scan_iter(match=f"{prefix}*", count=100):
                lote.append(str(clave))
                if len(lote) >= 100:
                    await self._client.delete(*lote)
                    lote.clear()
            if lote:
                await self._client.delete(*lote)

        try:
            await asyncio.wait_for(_escanear_y_borrar(), timeout=self._timeout)
        except (RedisError, TimeoutError, OSError) as exc:
            self._registrar_fallo("delete_prefix", exc)

    async def ping(self) -> bool:
        try:
            respuesta = await asyncio.wait_for(self._client.ping(), timeout=self._timeout)
            return bool(respuesta)
        except (RedisError, TimeoutError, OSError) as exc:
            self._registrar_fallo("ping", exc)
            return False

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except (RedisError, TimeoutError, OSError) as exc:
            self._registrar_fallo("close", exc)
