"""Endpoint HTTP POST /api/v1/content/locations desacoplado de adaptadores de BD."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from src.shared.http_module import problema, respuestas_documentadas

from ..services.ubicaciones_service import UbicacionesService
from .ubicaciones_dtos import UbicacionResponseDTO


def crear_router(
    administrador: Callable[..., Awaitable[Any]],
    servicio: Callable[[], UbicacionesService],
) -> APIRouter:
    """Compone el router de ubicaciones inyectando autorización y caso de uso."""
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
        actor_id = getattr(_admin, "id", None) or str(_admin)

        resultado = await servicio().crear(
            datos,
            imagen_bytes,
            imagen.content_type or "",
            idempotency_key,
            actor_id=actor_id,
        )
        return UbicacionResponseDTO(**resultado)

    return router
