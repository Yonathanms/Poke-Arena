"""Composición interna de casos de uso de Jugadores."""

from src.modules.identidad import identidad_module
from src.modules.motor_juego.domain.preparador_partida import MotorJuegoDeterminista
from src.shared.cache import get_cache
from src.shared.config import get_settings

from .coleccion_mazos.adapters.sql_coleccion_jugador import SqlColeccionJugador
from .coleccion_mazos.adapters.sql_entrega_inicial import SqlUnidadEntregaInicial
from .coleccion_mazos.controllers.coleccion_controller import crear_router_coleccion
from .coleccion_mazos.controllers.paquete_inicial_controller import (
    crear_router_paquete,
    provisionar_login,
)
from .coleccion_mazos.services.entrega_inicial_service import EntregaInicial
from .coleccion_mazos.services.paquete_inicial_service import (
    ColeccionJugadorService,
    PaqueteInicial,
)
from .emparejamiento.adapters.sql_emparejamiento import SqlRepositorioEmparejamiento
from .emparejamiento.controllers.emparejamiento_controller import crear_router_emparejamiento
from .emparejamiento.services.bot_service import ControladorBot
from .emparejamiento.services.emparejamiento_service import EmparejamientoService
from .gestion_decks.adapters.sql_decks import SqlRepositorioDecks
from .gestion_decks.controllers.decks_controller import crear_router_decks
from .gestion_decks.services.decks_service import DecksService
from .partidas.adapters.sql_partidas import (
    SqlFuenteCatalogoPartida,
    SqlRepositorioPartidas,
    SqlVerificadorDeckEnUso,
)
from .partidas.controllers.partidas_controller import crear_router_partidas
from .partidas.services.partidas_service import PartidasService


def crear_servicio_entrega_inicial() -> EntregaInicial:
    """Conecta la provisión con la fábrica SQL y la política central de Identidad."""
    return EntregaInicial(_unidad())


def crear_servicio_paquete() -> PaqueteInicial:
    """Conecta la consulta y apertura con la misma unidad de trabajo SQL."""
    return PaqueteInicial(_unidad())


def crear_servicio_coleccion() -> ColeccionJugadorService:
    """Compone la lectura de colección personal con su adaptador SQL."""
    from src.database.postgresql.connection import AsyncSessionLocal

    return ColeccionJugadorService(SqlColeccionJugador(AsyncSessionLocal))


def _unidad() -> SqlUnidadEntregaInicial:
    from src.database.postgresql.connection import AsyncSessionLocal

    return SqlUnidadEntregaInicial(AsyncSessionLocal, identidad_module.crear_autorizacion_coleccion)


def crear_servicio_decks() -> DecksService:
    """Compone DecksService con bloqueo de edición/borrado cuando está en uso."""
    from src.database.postgresql.connection import AsyncSessionLocal

    return DecksService(
        SqlRepositorioDecks(AsyncSessionLocal),
        verificador_en_uso=SqlVerificadorDeckEnUso(AsyncSessionLocal),
    )


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


async def provisionar_google(token: str) -> None:
    """Ejecuta el callback HTTP para un login Google ya confirmado."""
    await provisionar_login(crear_servicio_entrega_inicial(), token)


router_paquete, requerir_jugador_habilitado = crear_router_paquete(
    crear_servicio_paquete, identidad_module.requerir_jugador
)

router_decks = crear_router_decks(crear_servicio_decks, requerir_jugador_habilitado)
router_coleccion = crear_router_coleccion(crear_servicio_coleccion, requerir_jugador_habilitado)
router_partidas = crear_router_partidas(crear_servicio_partidas, requerir_jugador_habilitado)
router_emparejamiento = crear_router_emparejamiento(
    crear_servicio_emparejamiento, requerir_jugador_habilitado
)
