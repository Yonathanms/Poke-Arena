"""Worker reconciliador periódico PostgreSQL -> MongoDB, centralizado en la API principal.

La aplicación escribe directamente en PostgreSQL (ACID) y luego en MongoDB sin depender
de este worker para operar. Este componente complementario se ejecuta en segundo plano
dentro del ciclo de vida de FastAPI cada N segundos (por defecto 600 s = 10 minutos)
para verificar la concordancia de cartas y ubicaciones y restaurar cualquier desfase.
"""

import asyncio
import logging
from typing import Any, Protocol

from src.modules.catalogo.catalogo_module import (
    componer_reconciliador_cartas,
    componer_reconciliador_ubicaciones,
)
from src.shared.config import get_settings

logger = logging.getLogger("pokearena.reconciliador")


class ReconciliadorEntidadPort(Protocol):
    """Contrato común para reconciliadores de entidades SQL -> MongoDB."""

    async def conciliar(self) -> Any:
        """Compara PostgreSQL contra MongoDB y sincroniza registros faltantes o distintos."""
        ...


class ReconciliadorSQLMongo:
    """Orquesta la reconciliación periódica de cartas y ubicaciones."""

    def __init__(
        self,
        reconciliador_cartas: ReconciliadorEntidadPort,
        reconciliador_ubicaciones: ReconciliadorEntidadPort,
    ) -> None:
        self._reconciliadores: tuple[tuple[str, ReconciliadorEntidadPort], ...] = (
            ("cartas", reconciliador_cartas),
            ("ubicaciones", reconciliador_ubicaciones),
        )

    async def ejecutar_ciclo(self) -> dict[str, Any]:
        """Ejecuta una pasada completa aislando errores entre entidades."""
        resultados: dict[str, Any] = {}
        for nombre, reconciliador in self._reconciliadores:
            try:
                resultados[nombre] = await reconciliador.conciliar()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Ciclo de reconciliación falló para %s: %s", nombre, exc)
                resultados[nombre] = None
        return resultados


def crear_reconciliador_sql_mongo() -> ReconciliadorSQLMongo:
    """Compone el reconciliador con las conexiones oficiales de la API."""
    return ReconciliadorSQLMongo(
        reconciliador_cartas=componer_reconciliador_cartas(),
        reconciliador_ubicaciones=componer_reconciliador_ubicaciones(),
    )


async def iniciar_bucle_reconciliacion(
    detener: asyncio.Event,
    intervalo_segundos: float | None = None,
) -> None:
    """Bucle en segundo plano administrado por el lifespan de FastAPI."""
    intervalo = (
        intervalo_segundos
        if intervalo_segundos is not None
        else get_settings().RECONCILIATION_INTERVAL_SECONDS
    )
    reconciliador = crear_reconciliador_sql_mongo()
    logger.info("Worker reconciliador SQL->MongoDB iniciado (intervalo=%.0fs)", intervalo)

    try:
        while not detener.is_set():
            await reconciliador.ejecutar_ciclo()
            try:
                await asyncio.wait_for(detener.wait(), timeout=intervalo)
            except TimeoutError:
                pass
    except asyncio.CancelledError:
        logger.info("Worker reconciliador SQL->MongoDB detenido")
        raise
