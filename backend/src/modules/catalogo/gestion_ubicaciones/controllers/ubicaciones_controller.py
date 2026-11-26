"""Endpoint HTTP POST /api/v1/content/locations desacoplado de adaptadores de BD."""

import json
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, Path, Response, UploadFile, status

from src.shared.http_module import problema, respuestas_documentadas

from ..ports.ubicaciones_ports import ErrorImagenUbicacion
from ..services.ubicaciones_service import UbicacionesService
from .ubicaciones_dtos import UbicacionResponseDTO


def _respuesta_imagen_ubicacion(
    datos: bytes | None,
    codigo_no_encontrada: str,
    mensaje: str,
) -> Response:
    if datos is None:
        raise problema(404, codigo_no_encontrada, mensaje)
    media_type = "image/webp" if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP" else "image/png"
    return Response(
        datos,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300", "Vary": "Authorization"},
    )


def crear_router(
    administrador: Callable[..., Awaitable[Any]],
    servicio: Callable[[], UbicacionesService],
    jugador: Callable[..., Awaitable[Any]] | None = None,
    imagen_grande: Callable[[str], Awaitable[bytes | None]] | None = None,
    miniatura: Callable[[str], Awaitable[bytes | None]] | None = None,
) -> APIRouter:
    """Compone el router de ubicaciones inyectando autorización, caso de uso y lectura de medios."""
    router = APIRouter()
    auth_jugador = jugador if jugador is not None else administrador

    if imagen_grande is not None:
        @router.get(
            "/content/locations/{location_id}/image",
            response_class=Response,
            tags=["Content Locations"],
            summary="Obtener imagen completa WebP de una ubicación",
            responses={
                200: {
                    "content": {"image/webp": {"schema": {"type": "string", "format": "binary"}}},
                },
                **respuestas_documentadas({
                    401: "Sesión requerida",
                    403: "Rol insuficiente",
                    404: "Imagen de ubicación no encontrada",
                    503: "Medios no disponibles",
                }),
            },
        )
        async def obtener_imagen_ubicacion(
            location_id: Annotated[str, Path(min_length=1, max_length=36)],
            _actor: Any = Depends(auth_jugador),
        ) -> Response:
            try:
                datos = await imagen_grande(location_id)
            except ErrorImagenUbicacion:
                raise problema(
                    503,
                    "imagen_ubicacion_no_disponible",
                    "Imagen de ubicación no disponible.",
                ) from None
            return _respuesta_imagen_ubicacion(
                datos,
                "imagen_ubicacion_no_encontrada",
                "Imagen de ubicación no encontrada.",
            )

    if miniatura is not None:
        @router.get(
            "/content/locations/{location_id}/thumbnail",
            response_class=Response,
            tags=["Content Locations"],
            summary="Obtener miniatura WebP de una ubicación",
            responses={
                200: {
                    "content": {"image/webp": {"schema": {"type": "string", "format": "binary"}}},
                },
                **respuestas_documentadas({
                    401: "Sesión requerida",
                    403: "Rol insuficiente",
                    404: "Miniatura de ubicación no encontrada",
                    503: "Medios no disponibles",
                }),
            },
        )
        async def obtener_miniatura_ubicacion(
            location_id: Annotated[str, Path(min_length=1, max_length=36)],
            _actor: Any = Depends(auth_jugador),
        ) -> Response:
            try:
                datos = await miniatura(location_id)
            except ErrorImagenUbicacion:
                raise problema(
                    503,
                    "miniatura_ubicacion_no_disponible",
                    "Miniatura de ubicación no disponible.",
                ) from None
            return _respuesta_imagen_ubicacion(
                datos,
                "miniatura_ubicacion_no_encontrada",
                "Miniatura de ubicación no encontrada.",
            )

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
