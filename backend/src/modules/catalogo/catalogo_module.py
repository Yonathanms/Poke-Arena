"""Composición SQL sin registrar API, conectar motores ni activar workers.

Punto único de composición y carga para gestion_cartas.
"""

from importlib import import_module
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.postgresql.base import Base
from src.shared.idempotencia.models import IdempotencyRecordORM
from src.shared.outbox import OutboxEventORM

_PAQUETE = f"{__package__}.gestion_cartas"
dominio_cartas = import_module(f"{_PAQUETE}.domain.carta_model")
puertos_cartas = import_module(f"{_PAQUETE}.ports.cartas_ports")
dominio_imagenes = import_module(f"{_PAQUETE}.domain.imagen_model")
puertos_imagenes = import_module(f"{_PAQUETE}.ports.imagen_ports")
aplicacion_cartas = import_module(f"{_PAQUETE}.services.cartas_service")
persistencia_creacion = import_module(f"{_PAQUETE}.adapters.sql_creacion_carta")
proyeccion_domain = import_module(f"{_PAQUETE}.domain.proyeccion_carta")
outbox_sql = import_module(f"{_PAQUETE}.adapters.sql_outbox_repository")
outbox_mongo = import_module(f"{_PAQUETE}.adapters.mongo_card_projection")
outbox_app = import_module(f"{_PAQUETE}.services.proyeccion_service")
_orm = import_module(f"{_PAQUETE}.adapters.cartas_orm")
_repositorio = import_module(f"{_PAQUETE}.adapters.sql_carta_repository")


def modelos_persistencia() -> tuple[type[Base], ...]:
    """Expone seis mapeos únicos sin DDL; metadata parcial no apta para autogenerate."""
    return (
        _orm.CartaORM, _orm.HabilidadORM, _orm.ImagenCartaORM, _orm.ContadorCartaORM,
        IdempotencyRecordORM, OutboxEventORM,
    )


def crear_repositorio_cartas(session: AsyncSession) -> Any:
    """Inyecta sesión, sin transacciones ni HTTP; frontera dinámica explícita.

    Any está limitado a esta composición: importlib devuelve módulos sin tipos
    estáticos de sus miembros. El adaptador implementa el puerto tipado original,
    verificado por Mypy con su nombre de módulo y por pruebas de composición.
    """
    return _repositorio.SqlCartaRepository(session)


def crear_procesador_imagenes() -> Any:
    """Compone el procesador local sin requerir un event loop ni bases."""
    modulo = import_module(f"{_PAQUETE}.adapters.imagen_carta_adapter")
    return modulo.ProcesadorImagenPillow()


def crear_almacen_imagenes() -> Any:
    """Compone GridFS en el loop activo mediante el cliente oficial."""
    from gridfs import AsyncGridFSBucket

    from src.database.mongodb.connection import get_mongo_db
    from src.shared.config import get_settings

    modulo = import_module(f"{_PAQUETE}.adapters.mongo_carta_repository")
    bucket = AsyncGridFSBucket(get_mongo_db(), bucket_name=get_settings().MONGO_GRIDFS_BUCKET)
    return modulo.AlmacenImagenGridFS(bucket, crear_procesador_imagenes())


def crear_servicio_crear_carta() -> Any:
    """Compone el caso de uso para Python, con los clientes oficiales."""
    from src.database.postgresql.connection import AsyncSessionLocal, engine

    return aplicacion_cartas.CrearCarta(
        persistencia_creacion.SqlCoordinacionCreacion(engine, AsyncSessionLocal),
        crear_procesador_imagenes(),
        crear_almacen_imagenes(),
    )


def router_cartas(administrador: Any, jugador: Any = None) -> Any:
    """Compone el router del catálogo con la autorización pública de identidad."""
    modulo = import_module(f"{_PAQUETE}.controllers.cartas_controller")
    return modulo.crear_router(
        administrador, crear_servicio_crear_carta, listar_habilidades, jugador=jugador
    )


def router_ubicaciones(administrador: Any | None = None) -> Any:
    """Compone el router de ubicaciones con autorización."""
    from .gestion_ubicaciones.controllers.ubicaciones_controller import crear_router, router
    if administrador is not None:
        return crear_router(administrador)
    return router


def componer_procesador_outbox() -> tuple[Any, Any, type[Exception]]:
    """Compone el consumidor 1F con las conexiones oficiales y el índice existente."""
    from src.database.mongodb.connection import get_mongo_db
    from src.database.mongodb.destinos_outbox import MONGO_F5_BASE
    from src.database.postgresql.connection import AsyncSessionLocal
    from src.shared.config import get_settings

    ajustes = get_settings()
    db = get_mongo_db(conexion_directa=ajustes.MONGO_DB == MONGO_F5_BASE)
    almacen = outbox_mongo.MongoProyeccionCartas(db["cards_projection"])
    repo = outbox_sql.SqlOutboxCartas(
        AsyncSessionLocal, ajustes.OUTBOX_LEASE_SECONDS, ajustes.OUTBOX_MAX_ATTEMPTS
    )
    return (
        outbox_app.ProcesadorOutbox(repo, almacen, ajustes.OUTBOX_RETRY_MAX_SECONDS),
        almacen,
        proyeccion_domain.OutboxTemporal,
    )


async def listar_habilidades() -> list[tuple[str, str]]:
    """Compone la lectura administrativa con el repositorio y la sesión oficiales."""
    from src.database.postgresql.connection import transactional_session

    async with transactional_session() as sesion:
        repo = crear_repositorio_cartas(sesion)
        filas = await repo.listar_habilidades()
        return list(filas)


__all__ = [
    "componer_procesador_outbox",
    "crear_almacen_imagenes",
    "crear_procesador_imagenes",
    "crear_repositorio_cartas",
    "crear_servicio_crear_carta",
    "listar_habilidades",
    "modelos_persistencia",
    "router_cartas",
    "router_ubicaciones",
]
