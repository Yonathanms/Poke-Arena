"""Endpoints HTTP de Partidas protegidos por RBAC y ETag/304 (US 4)."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Header, Request, Response

from src.modules.identidad.gestion_sesiones.domain.sesion_model import Principal
from src.modules.motor_juego.domain.modelos_partida import JugadorNoParticipaError
from src.shared.errores_rfc7807.respuestas import respuestas_documentadas
from src.shared.http_etag import respuesta_no_modificada
from src.shared.http_module import problema

from ..domain.partida_model import (
    PartidaNoDisponibleError,
    PartidaNoEncontradaError,
)
from ..services.partidas_service import PartidasService
from .partidas_dtos import PartidaActivaDTO, VistaPartidaDTO

logger = logging.getLogger(__name__)


def crear_router_partidas(
    servicio: Callable[[], PartidasService],
    requerir_jugador: Callable[..., Awaitable[Principal]],
) -> APIRouter:
    """Registra rutas de consulta de partidas activas con Fog of War y ETag."""
    router = APIRouter(prefix="/player", tags=["Matches"])
    errores = respuestas_documentadas({
        401: "Sesión inválida o revocada",
        403: "Cuenta sin acceso de jugador o paquete sin abrir",
        404: "Partida no encontrada",
        422: "Parámetros inválidos",
        500: "Error interno",
        503: "Servicio temporalmente no disponible",
    })

    @router.get(
        "/matches/active",
        response_model=PartidaActivaDTO,
        responses={204: {"description": "El jugador no tiene partida activa"}, **errores},
    )
    async def obtener_partida_activa(
        request: Request,
        response: Response,
        principal: Principal = Depends(requerir_jugador),
    ) -> PartidaActivaDTO | Response:
        """Retorna la partida IN_PROGRESS del jugador o 204 si no tiene ninguna."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        try:
            activa = await servicio().obtener_partida_activa(principal.id)
        except PartidaNoDisponibleError:
            raise problema(
                503,
                "partida_no_disponible",
                "No se pudo consultar tu partida activa.",
            ) from None
        except Exception:
            logger.exception("Error inesperado consultando partida activa user=%s", principal.id)
            raise problema(
                500,
                "error_partida_activa",
                "Error interno al consultar partida.",
            ) from None

        if activa is None:
            return Response(status_code=204, headers={"Cache-Control": "private, no-store"})

        response.headers["Cache-Control"] = "private, no-store"
        return PartidaActivaDTO(
            match_id=activa.match_id,
            context=activa.context,
            status=activa.status,
            is_bot_match=activa.is_bot_match,
            bet_cubes=activa.bet_cubes,
            turn_number=activa.turn_number,
            turn_duration_seconds=activa.turn_duration_seconds,
            turn_started_at=activa.turn_started_at,
            turn_ends_at=activa.turn_ends_at,
            state_version=activa.state_version,
        )

    @router.get(
        "/matches/{match_id}",
        response_model=VistaPartidaDTO,
        responses={304: {"description": "No modificado (ETag vigente)"}, **errores},
    )
    async def obtener_partida(
        match_id: str,
        request: Request,
        response: Response,
        principal: Principal = Depends(requerir_jugador),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ) -> VistaPartidaDTO | Response:
        """Retorna la vista Fog of War de la partida o 304 Not Modified si coincide ETag."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        try:
            resultado = await servicio().obtener_vista_partida(
                principal.id,
                match_id,
                if_none_match=if_none_match,
            )
        except (PartidaNoEncontradaError, JugadorNoParticipaError):
            raise problema(404, "partida_no_encontrada", "La partida no existe.") from None
        except PartidaNoDisponibleError:
            raise problema(
                503,
                "partida_no_disponible",
                "No se pudo consultar la partida.",
            ) from None
        except Exception:
            logger.exception(
                "Error inesperado consultando partida=%s user=%s", match_id, principal.id
            )
            raise problema(500, "error_partida", "Error interno al consultar la partida.") from None

        if resultado.not_modified:
            return respuesta_no_modificada(resultado.etag, "private, no-cache")

        response.headers["ETag"] = resultado.etag
        response.headers["Cache-Control"] = "private, no-cache"
        return VistaPartidaDTO.model_validate(resultado.payload)

    return router
