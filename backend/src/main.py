from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.database.mongodb.connection import close_mongo_connection, get_mongo_db
from src.database.postgresql.connection import engine
from src.modules.catalogo.catalogo_module import router as catalogo_router
from src.shared.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación FastAPI."""
    yield
    close_mongo_connection()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="API Monolítica Modular Hexagonal — Poké-Arena",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Siguiente paso: registrar módulos de la aplicación
app.include_router(catalogo_router, prefix=settings.API_V1_PREFIX)


@app.get(
    f"{settings.API_V1_PREFIX}/health",
    tags=["System"],
    status_code=status.HTTP_200_OK,
    summary="Verificar estado del sistema y conexiones a bases de datos",
)
async def health_check() -> dict[str, Any]:
    health_status: dict[str, Any] = {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "databases": {},
    }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["databases"]["postgres"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["databases"]["postgres"] = f"error: {e}"

    try:
        mongo_db = get_mongo_db()
        await mongo_db.command("ping")
        health_status["databases"]["mongodb"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["databases"]["mongodb"] = f"error: {e}"

    return health_status
