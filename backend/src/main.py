from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.modules.content.presentation.routers import content_router
from src.shared.infrastructure.config import get_settings
from src.shared.infrastructure.database import (
    Base,
    read_engine,
    write_engine,
)
from src.shared.infrastructure.mongo import close_mongo_connection, get_mongo_db
from src.shared.presentation.exception_handlers import register_exception_handlers
from src.shared.presentation.middlewares.correlation_id import (
    CorrelationIdMiddleware,
    get_current_correlation_id,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación: inicialización y apagado limpio."""
    # 1. Startup: Crear tablas en PostgreSQL (Master) si no existen
    async with write_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Inicializar índices en MongoDB
    mongo_db = get_mongo_db()
    await mongo_db["cards_projection"].create_index([("name", "text")])
    await mongo_db["cards_projection"].create_index([("card_type", 1)])
    await mongo_db["cards_projection"].create_index([("cost", 1)])
    await mongo_db["cards_projection"].create_index([("code", 1)], unique=True)

    yield

    # 3. Shutdown: Cerrar conexiones
    close_mongo_connection()
    await write_engine.dispose()
    await read_engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="API Monolítica Modular con Arquitectura Hexagonal para Poké-Arena (Sprint 1)",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ------------------------------------------------------------------------------
# Middlewares
# ------------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

app.add_middleware(CorrelationIdMiddleware)

# ------------------------------------------------------------------------------
# Manejador Global de Excepciones (RFC 7807)
# ------------------------------------------------------------------------------
register_exception_handlers(app)

# ------------------------------------------------------------------------------
# Registro de Routers Modulares
# ------------------------------------------------------------------------------
app.include_router(content_router, prefix=settings.API_V1_PREFIX)


# ------------------------------------------------------------------------------
# Health Check Endpoint
# ------------------------------------------------------------------------------
@app.get(
    f"{settings.API_V1_PREFIX}/health",
    tags=["System"],
    status_code=status.HTTP_200_OK,
    summary="Verificar el estado del sistema y conexiones a bases de datos",
)
async def health_check() -> dict[str, Any]:
    health_status: dict[str, Any] = {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "correlation_id": get_current_correlation_id(),
        "databases": {},
    }

    # Verificar PostgreSQL Master
    try:
        async with write_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["databases"]["postgres_master"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["databases"]["postgres_master"] = f"error: {str(e)}"

    # Verificar PostgreSQL Réplica
    try:
        async with read_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["databases"]["postgres_replica"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["databases"]["postgres_replica"] = f"error: {str(e)}"

    # Verificar MongoDB
    try:
        mongo_db = get_mongo_db()
        await mongo_db.command("ping")
        health_status["databases"]["mongodb"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["databases"]["mongodb"] = f"error: {str(e)}"

    return health_status
