"""Composición interna de casos de uso del Módulo Jugadores (Perfiles, Colección y Decks)."""

from collections.abc import Callable

from fastapi import APIRouter

from src.modules.identidad import identidad_module

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
from .gestion_decks.adapters.sql_decks import SqlRepositorioDecks
from .gestion_decks.controllers.decks_controller import crear_router_decks
from .gestion_decks.ports.deck_ports import VerificadorDeckEnUsoPort
from .gestion_decks.services.decks_service import DecksService


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


def crear_servicio_decks(
    verificador_en_uso: VerificadorDeckEnUsoPort | None = None,
) -> DecksService:
    """Compone DecksService recibiendo opcionalmente el puerto invertido de uso activo."""
    from src.database.postgresql.connection import AsyncSessionLocal

    return DecksService(
        SqlRepositorioDecks(AsyncSessionLocal),
        verificador_en_uso=verificador_en_uso,
    )


async def provisionar_google(token: str) -> None:
    """Ejecuta el callback HTTP para un login Google ya confirmado."""
    await provisionar_login(crear_servicio_entrega_inicial(), token)


router_paquete, requerir_jugador_habilitado = crear_router_paquete(
    crear_servicio_paquete, identidad_module.requerir_jugador
)

router_coleccion = crear_router_coleccion(crear_servicio_coleccion, requerir_jugador_habilitado)


def crear_router_decks_jugador(
    verificador_en_uso: Callable[[], VerificadorDeckEnUsoPort] | None = None,
) -> APIRouter:
    """Compone el router de decks inyectando el verificador externo sin acoplar módulos."""

    def _servicio() -> DecksService:
        return crear_servicio_decks(
            verificador_en_uso() if verificador_en_uso is not None else None
        )

    return crear_router_decks(_servicio, requerir_jugador_habilitado)
