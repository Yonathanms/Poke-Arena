"""Composición interna de casos de uso de Jugadores."""

from src.modules.identidad import identidad_module

from .coleccion_mazos.adapters.sql_entrega_inicial import SqlUnidadEntregaInicial
from .coleccion_mazos.controllers.coleccion_controller import crear_router_coleccion
from .coleccion_mazos.controllers.paquete_inicial_controller import (
    crear_router_paquete,
    provisionar_login,
)
from .coleccion_mazos.services.entrega_inicial_service import EntregaInicial
from .coleccion_mazos.services.paquete_inicial_service import PaqueteInicial
from .gestion_decks.adapters.sql_decks import SqlRepositorioDecks
from .gestion_decks.controllers.decks_controller import crear_router_decks
from .gestion_decks.services.decks_service import DecksService


def crear_servicio_entrega_inicial() -> EntregaInicial:
    """Conecta la provisión con la fábrica SQL y la política central de Identidad."""
    return EntregaInicial(_unidad())


def crear_servicio_paquete() -> PaqueteInicial:
    """Conecta la consulta y apertura con la misma unidad de trabajo SQL."""
    return PaqueteInicial(_unidad())


def _unidad() -> SqlUnidadEntregaInicial:
    from src.database.postgresql.connection import AsyncSessionLocal

    return SqlUnidadEntregaInicial(AsyncSessionLocal, identidad_module.crear_autorizacion_coleccion)


def crear_servicio_decks() -> DecksService:
    from src.database.postgresql.connection import AsyncSessionLocal

    return DecksService(SqlRepositorioDecks(AsyncSessionLocal))


async def provisionar_google(token: str) -> None:
    """Ejecuta el callback HTTP para un login Google ya confirmado."""
    await provisionar_login(crear_servicio_entrega_inicial(), token)


router_paquete, requerir_jugador_habilitado = crear_router_paquete(
    crear_servicio_paquete, identidad_module.requerir_jugador
)

router_decks = crear_router_decks(crear_servicio_decks, requerir_jugador_habilitado)
router_coleccion = crear_router_coleccion(requerir_jugador_habilitado)
