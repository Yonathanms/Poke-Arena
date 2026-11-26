"""Composición interna del Módulo Partidas y Emparejamiento (Capa 3).

Único punto de composición para:
- Gestor de Emparejamiento (cola Elo expansiva, heartbeat, cancelación)
- Orquestador de Partida (ciclo de vida, snapshots, apuesta, Fog of War)
- Controlador Bot (oferta tras 60 s bajo las mismas reglas de partida)
- Adaptador SqlVerificadorDeckEnUso (puerto invertido inyectado en Jugadores desde main.py)
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter

from src.modules.identidad.gestion_sesiones.domain.sesion_model import Principal
from src.modules.motor_juego.domain.preparador_partida import MotorJuegoDeterminista
from src.shared.cache import get_cache
from src.shared.config import get_settings

from .emparejamiento.adapters.sql_emparejamiento import SqlRepositorioEmparejamiento
from .emparejamiento.controllers.emparejamiento_controller import crear_router_emparejamiento
from .emparejamiento.services.bot_service import ControladorBot
from .emparejamiento.services.emparejamiento_service import EmparejamientoService
from .partidas.adapters.sql_partidas import (
    SqlFuenteCatalogoPartida,
    SqlRepositorioPartidas,
    SqlVerificadorDeckEnUso,
)
from .partidas.controllers.partidas_controller import crear_router_partidas
from .partidas.services.partidas_service import PartidasService


def crear_verificador_deck_en_uso() -> SqlVerificadorDeckEnUso:
    """Compone el adaptador SQL que implementa VerificadorDeckEnUsoPort."""
    from src.database.postgresql.connection import AsyncSessionLocal

    return SqlVerificadorDeckEnUso(AsyncSessionLocal)


def crear_servicio_partidas() -> PartidasService:
    """Compone PartidasService con PostgreSQL ACID, MotorJuego puro y caché ADR-003."""
    from src.database.postgresql.connection import AsyncSessionLocal

    settings = get_settings()
    return PartidasService(
        repo=SqlRepositorioPartidas(AsyncSessionLocal),
        catalogo=SqlFuenteCatalogoPartida(),
        motor=MotorJuegoDeterminista(),
        cache=get_cache(),
        turn_duration_seconds=settings.MATCH_TURN_DURATION_SECONDS,
        ranked_initial_bet=settings.MATCH_RANKED_INITIAL_BET,
    )


def crear_servicio_emparejamiento() -> EmparejamientoService:
    """Compone EmparejamientoService con cola ACID, Bot y caché condicional."""
    from src.database.postgresql.connection import AsyncSessionLocal

    settings = get_settings()
    return EmparejamientoService(
        repo=SqlRepositorioEmparejamiento(AsyncSessionLocal),
        partidas=crear_servicio_partidas(),
        bot=ControladorBot(SqlFuenteCatalogoPartida()),
        cache=get_cache(),
        heartbeat_timeout_seconds=settings.MATCHMAKING_HEARTBEAT_TIMEOUT_SECONDS,
        bot_offer_seconds=settings.MATCHMAKING_BOT_OFFER_SECONDS,
        max_elo_diff=settings.MATCHMAKING_MAX_ELO_DIFF,
        ranked_min_cubes=settings.MATCH_RANKED_MIN_CUBES,
    )


def crear_routers_partidas_emparejamiento(
    requerir_jugador_habilitado: Callable[..., Awaitable[Principal]],
) -> tuple[APIRouter, APIRouter]:
    """Compone los routers de emparejamiento y partidas protegidos por RBAC."""
    router_emparejamiento = crear_router_emparejamiento(
        crear_servicio_emparejamiento, requerir_jugador_habilitado
    )
    router_partidas = crear_router_partidas(
        crear_servicio_partidas, requerir_jugador_habilitado
    )
    return router_emparejamiento, router_partidas


__all__ = [
    "crear_routers_partidas_emparejamiento",
    "crear_servicio_emparejamiento",
    "crear_servicio_partidas",
    "crear_verificador_deck_en_uso",
]
