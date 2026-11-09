"""Endpoint POST /api/v1/content/locations con multipart y autorización."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.postgresql.connection import get_db
from src.shared.http_module import problema, respuestas_documentadas

from ..adapters.imagen_ubicacion_adapter import ImagenUbicacionAdapter
from ..adapters.sql_ubicacion_repository import SqlUbicacionRepository
from ..services.ubicaciones_service import UbicacionesService
from .ubicaciones_dtos import UbicacionResponseDTO


def _get_service(db: AsyncSession) -> UbicacionesService:
    imagen_adapter = ImagenUbicacionAdapter()
    sql_repo = SqlUbicacionRepository(db)
    return UbicacionesService(imagen_adapter, sql_repo)


def crear_router(administrador: Callable[..., Awaitable[Any]]) -> APIRouter:
    """Compone el router de ubicaciones inyectando el guard de autorización oficial."""
    router = APIRouter()

    @router.post(
        "/content/locations",
        status_code=status.HTTP_201_CREATED,
        response_model=UbicacionResponseDTO,
        summary="Crear una nueva ubicación de arena",
        responses=respuestas_documentadas({
            401: "Sesión requerida",
            403: "Rol insuficiente",
            422: "Parámetros o imagen inválidos",
        }),
    )
    async def crear_ubicacion(
        nombre: str = Form(..., max_length=100),
        descripcion: str = Form(..., max_length=500),
        card_limit: int = Form(..., ge=0, le=5),
        energia_tipo: str = Form(...),
        energia_valor: int = Form(..., ge=0),
        efecto_tipo: str = Form(...),
        efecto_params: str = Form(...),
        imagen: UploadFile = File(...),
        idempotency_key: str = Header(..., alias="idempotency-key"),
        db: AsyncSession = Depends(get_db),
        _admin: Any = Depends(administrador),
    ) -> UbicacionResponseDTO:
        try:
            params_dict = json.loads(efecto_params)
        except (json.JSONDecodeError, ValueError):
            raise problema(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "efecto_params_invalido",
                "efecto_params debe ser un JSON válido.",
            ) from None

        datos = {
            "nombre": nombre,
            "descripcion": descripcion,
            "card_limit": card_limit,
            "energia_tipo": energia_tipo,
            "energia_valor": energia_valor,
            "efecto_tipo": efecto_tipo,
            "efecto_params": params_dict,
        }

        imagen_bytes = await imagen.read()
        service = _get_service(db)

        resultado = await service.crear(
            datos, imagen_bytes, imagen.content_type or "", idempotency_key
        )
        return UbicacionResponseDTO(**resultado)

    return router


# Router por defecto para compatibilidad
router = crear_router(lambda: "admin-default")
