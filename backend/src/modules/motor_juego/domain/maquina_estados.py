"""Máquinas de estados declarativas del dominio de juego (RNF-INT-05, RNF-ARQ-01).

Módulo de dominio 100% puro: sin dependencias de SQL, MongoDB, FastAPI, reloj ni azar.
Define las tablas oficiales de transiciones válidas para búsqueda, partida y turno.
"""

from enum import StrEnum

from src.shared.maquina_estados import MaquinaEstados, TransicionInvalida


class EstadoBusqueda(StrEnum):
    """Ciclo de vida de una solicitud de búsqueda de partida (US 2 y US 3)."""

    SEARCHING = "SEARCHING"
    MATCHED = "MATCHED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class EventoBusqueda(StrEnum):
    """Eventos autorizados sobre una búsqueda de partida."""

    EMPAREJAR = "EMPAREJAR"
    ACEPTAR_BOT = "ACEPTAR_BOT"
    CANCELAR = "CANCELAR"
    EXPIRAR = "EXPIRAR"


MAQUINA_ESTADOS_BUSQUEDA: MaquinaEstados[EstadoBusqueda, EventoBusqueda] = MaquinaEstados({
    (EstadoBusqueda.SEARCHING, EventoBusqueda.EMPAREJAR): EstadoBusqueda.MATCHED,
    (EstadoBusqueda.SEARCHING, EventoBusqueda.ACEPTAR_BOT): EstadoBusqueda.MATCHED,
    (EstadoBusqueda.SEARCHING, EventoBusqueda.CANCELAR): EstadoBusqueda.CANCELLED,
    (EstadoBusqueda.SEARCHING, EventoBusqueda.EXPIRAR): EstadoBusqueda.EXPIRED,
})


class EstadoPartida(StrEnum):
    """Ciclo de vida de una partida (US 4 y futuras historias de combate)."""

    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    ABORTED = "ABORTED"


class EventoPartida(StrEnum):
    """Eventos autorizados sobre una partida."""

    FINALIZAR = "FINALIZAR"
    ABORTAR = "ABORTAR"


MAQUINA_ESTADOS_PARTIDA: MaquinaEstados[EstadoPartida, EventoPartida] = MaquinaEstados({
    (EstadoPartida.IN_PROGRESS, EventoPartida.FINALIZAR): EstadoPartida.FINISHED,
    (EstadoPartida.IN_PROGRESS, EventoPartida.ABORTAR): EstadoPartida.ABORTED,
})


class EstadoTurno(StrEnum):
    """Ciclo de vida de un turno dentro de una partida."""

    PLANNING = "PLANNING"
    RESOLVING = "RESOLVING"
    COMPLETED = "COMPLETED"


class EventoTurno(StrEnum):
    """Eventos autorizados sobre un turno."""

    INICIAR_RESOLUCION = "INICIAR_RESOLUCION"
    COMPLETAR = "COMPLETAR"


MAQUINA_ESTADOS_TURNO: MaquinaEstados[EstadoTurno, EventoTurno] = MaquinaEstados({
    (EstadoTurno.PLANNING, EventoTurno.INICIAR_RESOLUCION): EstadoTurno.RESOLVING,
    (EstadoTurno.RESOLVING, EventoTurno.COMPLETAR): EstadoTurno.COMPLETED,
})

__all__ = [
    "EstadoBusqueda",
    "EstadoPartida",
    "EstadoTurno",
    "EventoBusqueda",
    "EventoPartida",
    "EventoTurno",
    "MAQUINA_ESTADOS_BUSQUEDA",
    "MAQUINA_ESTADOS_PARTIDA",
    "MAQUINA_ESTADOS_TURNO",
    "TransicionInvalida",
]
