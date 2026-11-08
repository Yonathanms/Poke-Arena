from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from src.modules.catalogo.catalogo_module import catalogo_router
from src.shared.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación FastAPI."""
    yield
    # Conexiones se gestionan de forma segura si están activas
    try:
        from src.database.mongodb.connection import close_mongo_connection
        close_mongo_connection()
    except Exception:
        pass


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

# Rutas de la API v1
app.include_router(catalogo_router, prefix=settings.API_V1_PREFIX)


@app.get(
    f"{settings.API_V1_PREFIX}/health",
    tags=["System"],
    status_code=status.HTTP_200_OK,
    summary="Verificar estado del sistema y endpoints",
)
async def health_check() -> dict[str, Any]:
    health_status: dict[str, Any] = {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "catalogo": "ready",
    }
    return health_status
