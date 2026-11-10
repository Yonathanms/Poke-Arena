"""Punto de entrada FastAPI y composición de los módulos HTTP."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.database.mongodb.connection import (
    close_mongo_connection,
    get_mongo_db,
    verificar_mongo_original,
)
from src.database.postgresql.destino_original import IDENTIDAD_SQL, destino_original_activo
from src.database.postgresql.revisiones import REVISION_TIPO_CUENTA
from src.modules.catalogo.catalogo_module import router_cartas, router_ubicaciones
from src.modules.identidad import identidad_module
from src.modules.jugadores.jugadores_module import provisionar_google, router_paquete
from src.shared.config import get_settings
from src.shared.http_module import registrar_errores


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación FastAPI con sincronización outbox automática."""
    import asyncio
    import logging
    from src.database.postgresql.connection import engine
    from src.modules.catalogo.catalogo_module import componer_procesador_outbox

    logger = logging.getLogger("pokearena.outbox_worker")
    detener_outbox = asyncio.Event()
    tarea_outbox: asyncio.Task[None] | None = None

    async def _bucle_outbox():
        try:
            procesador, almacen, err_temp = componer_procesador_outbox()
            await almacen.verificar_indices()
            while not detener_outbox.is_set():
                try:
                    await procesador.lote(50, 5, detener_outbox)
                except Exception as ex:
                    logger.debug("Reintento outbox en segundo plano: %s", ex)
                try:
                    await asyncio.wait_for(detener_outbox.wait(), timeout=1.5)
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Worker outbox en segundo plano interrumpido: %s", e)

    try:
        if get_settings().ORIGINAL_RUNTIME == "api":
            async with engine.connect() as conn:
                identidad = tuple((await conn.execute(IDENTIDAD_SQL)).one())
                if (
                    not destino_original_activo(identidad, "api")
                    or await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    != REVISION_TIPO_CUENTA
                ):
                    raise ValueError("destino_postgresql_original_no_autorizado")
            await verificar_mongo_original("api")

        tarea_outbox = asyncio.create_task(_bucle_outbox())
        yield
    finally:
        detener_outbox.set()
        if tarea_outbox is not None:
            tarea_outbox.cancel()
            try:
                await asyncio.wait_for(tarea_outbox, timeout=2.0)
            except (asyncio.CancelledError, TimeoutError, Exception):
                pass
        await close_mongo_connection()
        await engine.dispose()


def crear_app() -> FastAPI:
    """Registra módulos y políticas HTTP sin abrir conexiones."""
    settings = get_settings()
    settings.verificar_destinos("api")
    if settings.ORIGINAL_RUNTIME == "api" and (
        not settings.GOOGLE_OAUTH_CLIENT_ID
        or not (settings.admin_google_subjects or settings.admin_emails)
    ):
        raise ValueError("configuracion_administrativa_original_incompleta")
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="API Monolítica Modular Hexagonal — Poké-Arena",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Correlation-ID", "Retry-After"],
    )
    registrar_errores(app)
    app.include_router(
        identidad_module.crear_router_identidad(provisionar_google), prefix=settings.API_V1_PREFIX
    )
    app.include_router(router_paquete, prefix=settings.API_V1_PREFIX)
    app.include_router(
        router_cartas(
            identidad_module.requerir_administrador,
            identidad_module.requerir_jugador,
        ),
        prefix=settings.API_V1_PREFIX,
    )
    app.include_router(
        router_ubicaciones(identidad_module.requerir_administrador),
        prefix=settings.API_V1_PREFIX,
    )
    app.add_api_route(
        f"{settings.API_V1_PREFIX}/health",
        health_check,
        methods=["GET"],
        tags=["System"],
        status_code=status.HTTP_200_OK,
        summary="Verificar estado del sistema y conexiones a bases de datos",
    )
    return app


async def health_check() -> dict[str, Any]:
    """Prueba ambos motores sin exponer diagnósticos de conexión."""
    from src.database.postgresql.connection import engine

    health_status: dict[str, Any] = {
        "status": "healthy",
        "environment": get_settings().ENVIRONMENT,
        "databases": {},
    }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["databases"]["postgres"] = "connected"
    except Exception:
        health_status["status"] = "degraded"
        health_status["databases"]["postgres"] = "error: conexión PostgreSQL no disponible"

    try:
        mongo_db = get_mongo_db()
        await mongo_db.command("ping")
        health_status["databases"]["mongodb"] = "connected"
    except Exception:
        health_status["status"] = "degraded"
        health_status["databases"]["mongodb"] = "error: conexión MongoDB no disponible"

    return health_status


app = crear_app()
