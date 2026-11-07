"""Orquesta una entrega at-least-once sin transacción SQL durante MongoDB."""

import asyncio
import logging
from time import monotonic
from uuid import uuid4

from ..domain.proyeccion_carta import (
    EventoIncompatible,
    EventoReclamado,
    OutboxTemporal,
    ProyeccionTemporal,
)
from ..ports.proyeccion_ports import OutboxCartasPort, ProyeccionCartasPort

logger = logging.getLogger("pokearena.outbox_worker")


def demora_reintento(intento: int, tope: int) -> int:
    """Calcula backoff exponencial en segundos con un límite fijo."""
    return min(1 << min(intento, 16), tope)


class ProcesadorOutbox:
    """Consume solo CardCreated a través de los puertos de proyección."""

    def __init__(
        self, outbox: OutboxCartasPort, mongo: ProyeccionCartasPort, max_demora: int
    ) -> None:
        """Inyecta reclamación, proyección y tope de reintentos."""
        self._outbox, self._mongo, self._max_demora = outbox, mongo, max_demora
        self._worker = str(uuid4())

    async def _procesar(self, evento: EventoReclamado) -> bool:
        """Separa el resultado Mongo del resultado del commit de confirmación."""
        inicio = monotonic()
        error = None
        demora = None
        try:
            carta = await self._outbox.proyeccion(evento, evento.contenido())
            await self._mongo.guardar(carta)
        except EventoIncompatible as exc:
            error = str(exc)
        except (OutboxTemporal, ProyeccionTemporal):
            error = "dependencia_no_confirmada"
            demora = demora_reintento(evento.intento, self._max_demora)

        try:
            vigente = await self._outbox.resolver(evento, error, demora)
            estado = (
                "procesado"
                if vigente and error is None
                else ("fallo_registrado" if vigente else "lease_no_vigente")
            )
        except OutboxTemporal:
            # El commit puede haber tenido éxito. El lease y el estado durable deciden.
            estado = "confirmacion_incierta"
        logger.info(
            "worker=%s evento=%r tipo=%r carta=%r correlacion=%r intento=%d "
            "estado=%s error=%s duracion_ms=%d",
            self._worker,
            evento.id,
            evento.tipo,
            evento.agregado,
            evento.correlacion,
            evento.intento,
            estado,
            error,
            int((monotonic() - inicio) * 1000),
        )
        return estado == "procesado"

    async def lote(self, limite: int, concurrencia: int, detener: asyncio.Event) -> int:
        """Reclama únicamente el grupo que puede comenzar en ese momento."""
        procesados = 0
        restantes = limite
        while restantes > 0 and not detener.is_set():
            reclamados = await self._outbox.reclamar(min(restantes, concurrencia))
            if not reclamados:
                break
            async with asyncio.TaskGroup() as grupo:
                tareas = [grupo.create_task(self._procesar(evento)) for evento in reclamados]
            procesados += sum(tarea.result() for tarea in tareas)
            restantes -= len(reclamados)
        return procesados
