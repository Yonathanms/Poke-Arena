"""Composición SQL/NoSQL del módulo Catálogo.

Punto único de composición y carga para gestion_cartas y gestion_ubicaciones.
"""

from importlib import import_module
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.postgresql.base import Base
from src.shared.idempotencia.models import IdempotencyRecordORM

_PAQUETE = f"{__package__}.gestion_cartas"
dominio_cartas = import_module(f"{_PAQUETE}.domain.carta_model")
puertos_cartas = import_module(f"{_PAQUETE}.ports.cartas_ports")
dominio_imagenes = import_module(f"{_PAQUETE}.domain.imagen_model")
puertos_imagenes = import_module(f"{_PAQUETE}.ports.imagen_ports")
aplicacion_cartas = import_module(f"{_PAQUETE}.services.cartas_service")
persistencia_creacion = import_module(f"{_PAQUETE}.adapters.sql_creacion_carta")
proyeccion_domain = import_module(f"{_PAQUETE}.domain.proyeccion_carta")
fuente_cartas_sql = import_module(f"{_PAQUETE}.adapters.sql_outbox_repository")
proyeccion_mongo = import_module(f"{_PAQUETE}.adapters.mongo_card_projection")
reconciliador_cartas_app = import_module(f"{_PAQUETE}.services.proyeccion_service")
_orm = import_module(f"{_PAQUETE}.adapters.cartas_orm")
_repositorio = import_module(f"{_PAQUETE}.adapters.sql_carta_repository")


def modelos_persistencia() -> tuple[type[Base], ...]:
    """Expone los mapeos ORM de catálogo sin DDL."""
    return (
        _orm.CartaORM,
        _orm.HabilidadORM,
        _orm.ImagenCartaORM,
        _orm.ContadorCartaORM,
        IdempotencyRecordORM,
    )


def crear_repositorio_cartas(session: AsyncSession) -> Any:
    """Inyecta sesión SQL para operaciones de catálogo."""
    return _repositorio.SqlCartaRepository(session)


def crear_procesador_imagenes() -> Any:
    """Compone el procesador local Pillow sin requerir un event loop ni bases."""
    modulo = import_module(f"{_PAQUETE}.adapters.imagen_carta_adapter")
    return modulo.ProcesadorImagenPillow()


def crear_almacen_imagenes() -> Any:
    """Compone GridFS en el loop activo mediante el cliente PyMongo Async oficial."""
    from gridfs import AsyncGridFSBucket

    from src.database.mongodb.connection import get_mongo_db
    from src.shared.config import get_settings

    modulo = import_module(f"{_PAQUETE}.adapters.mongo_carta_repository")
    bucket = AsyncGridFSBucket(get_mongo_db(), bucket_name=get_settings().MONGO_GRIDFS_BUCKET)
    return modulo.AlmacenImagenGridFS(bucket, crear_procesador_imagenes())


def crear_proyeccion_cartas() -> Any:
    """Compone el adaptador MongoDB para escritura directa y reconciliación de cards_projection."""
    from src.database.mongodb.connection import get_mongo_db

    return proyeccion_mongo.MongoProyeccionCartas(get_mongo_db()["cards_projection"])


def crear_servicio_crear_carta() -> Any:
    """Compone CrearCarta con commit ACID en PostgreSQL y proyección directa a MongoDB."""
    from src.database.postgresql.connection import AsyncSessionLocal, engine

    return aplicacion_cartas.CrearCarta(
        persistencia_creacion.SqlCoordinacionCreacion(engine, AsyncSessionLocal),
        crear_procesador_imagenes(),
        crear_almacen_imagenes(),
        crear_proyeccion_cartas(),
    )


def router_cartas(administrador: Any, jugador: Any = None) -> Any:
    """Compone el router del catálogo con la autorización pública de identidad."""
    modulo = import_module(f"{_PAQUETE}.controllers.cartas_controller")
    return modulo.crear_router(
        administrador,
        crear_servicio_crear_carta,
        listar_habilidades,
        tipos=listar_tipos,
        rarezas=listar_rarezas,
        jugador=jugador,
        miniatura=recuperar_miniatura_carta,
        imagen_grande=recuperar_imagen_carta,
    )


async def recuperar_imagen_carta(carta_id: str) -> bytes | None:
    """Compone la consulta SQL y la lectura del bucket compartido para la imagen original."""
    from src.database.postgresql.connection import transactional_session

    async def buscar_referencia(identificador: str) -> str | None:
        async with transactional_session() as sesion:
            repo = crear_repositorio_cartas(sesion)
            referencia: str | None = await repo.buscar_referencia_original(identificador)
            return referencia

    referencia = await buscar_referencia(carta_id)
    if referencia is None:
        return None
    try:
        almacen = crear_almacen_imagenes()
        return await almacen.recuperar(referencia)
    except Exception:
        return None


async def recuperar_miniatura_carta(carta_id: str) -> bytes | None:
    """Compone la consulta SQL y la lectura del bucket compartido."""
    from src.database.postgresql.connection import transactional_session

    servicio = import_module(f"{_PAQUETE}.services.miniaturas_service")

    async def buscar_referencia(identificador: str) -> str | None:
        async with transactional_session() as sesion:
            repo = crear_repositorio_cartas(sesion)
            referencia: str | None = await repo.buscar_referencia_miniatura(identificador)
            return referencia

    datos: bytes | None = await servicio.recuperar_miniatura(
        carta_id,
        buscar_referencia,
        crear_almacen_imagenes(),
    )
    return datos


def router_ubicaciones(administrador: Any | None = None) -> Any:
    """Compone el router de ubicaciones con autorización."""
    from .gestion_ubicaciones.controllers.ubicaciones_controller import crear_router, router

    if administrador is not None:
        return crear_router(administrador)
    return router


def componer_reconciliador_cartas() -> Any:
    """Compone el reconciliador periódico SQL -> MongoDB para cartas."""
    from src.database.postgresql.connection import AsyncSessionLocal

    return reconciliador_cartas_app.ReconciliadorCartas(
        fuente_cartas_sql.SqlFuenteCartas(AsyncSessionLocal),
        crear_proyeccion_cartas(),
    )


def componer_reconciliador_ubicaciones() -> Any:
    """Compone el reconciliador periódico SQL -> MongoDB para ubicaciones."""
    from src.database.postgresql.connection import AsyncSessionLocal

    from .gestion_ubicaciones.adapters.mongo_ubicacion_repository import MongoUbicacionRepository
    from .gestion_ubicaciones.adapters.sql_ubicacion_repository import SqlFuenteUbicaciones
    from .gestion_ubicaciones.services.ubicaciones_service import ReconciliadorUbicaciones

    return ReconciliadorUbicaciones(
        SqlFuenteUbicaciones(AsyncSessionLocal),
        MongoUbicacionRepository(),
    )


async def listar_habilidades() -> list[tuple[str, str]]:
    """Compone la lectura administrativa con el repositorio y la sesión oficiales."""
    from src.database.postgresql.connection import transactional_session

    async with transactional_session() as sesion:
        repo = crear_repositorio_cartas(sesion)
        filas = await repo.listar_habilidades()
        return list(filas)


async def listar_tipos() -> list[tuple[str, str, str | None]]:
    """Compone la lectura de tipos con el repositorio y la sesión oficiales."""
    from src.database.postgresql.connection import transactional_session

    async with transactional_session() as sesion:
        repo = crear_repositorio_cartas(sesion)
        filas = await repo.listar_tipos()
        return list(filas)


async def listar_rarezas() -> list[tuple[str, str]]:
    """Compone la lectura de rarezas con el repositorio y la sesión oficiales."""
    from src.database.postgresql.connection import transactional_session

    async with transactional_session() as sesion:
        repo = crear_repositorio_cartas(sesion)
        filas = await repo.listar_rarezas()
        return list(filas)


__all__ = [
    "componer_reconciliador_cartas",
    "componer_reconciliador_ubicaciones",
    "crear_almacen_imagenes",
    "crear_procesador_imagenes",
    "crear_proyeccion_cartas",
    "crear_repositorio_cartas",
    "crear_servicio_crear_carta",
    "listar_habilidades",
    "listar_rarezas",
    "listar_tipos",
    "modelos_persistencia",
    "router_cartas",
    "router_ubicaciones",
]
