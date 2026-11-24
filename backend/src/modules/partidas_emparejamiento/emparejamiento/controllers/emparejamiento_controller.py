"""Endpoints HTTP de Emparejamiento y oferta de Bot protegidos por RBAC (US 2 y US 3)."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Header, Request, Response

from src.modules.identidad.gestion_sesiones.domain.sesion_model import Principal
from src.shared.errores_rfc7807.respuestas import respuestas_documentadas
from src.shared.http_etag import respuesta_no_modificada
from src.shared.http_module import problema

from ..domain.emparejamiento_model import (
    BotCatalogoInsuficienteError,
    BusquedaNoEncontradaError,
    BusquedaTerminalError,
    BusquedaVigenteOtroContextoError,
    BusquedaYaEmparejadaError,
    CubosInsuficientesError,
    DeckInvalidoBusquedaError,
    DeckNoEncontradoBusquedaError,
    EmparejamientoNoDisponibleError,
    OfertaBotNoDisponibleError,
    PartidaActivaError,
    ResultadoBusqueda,
)
from ..services.emparejamiento_service import EmparejamientoService
from .emparejamiento_dtos import BusquedaPartidaDTO, IniciarBusquedaRequest

logger = logging.getLogger(__name__)


def _a_dto(resultado: ResultadoBusqueda) -> BusquedaPartidaDTO:
    b = resultado.busqueda
    assert b is not None
    return BusquedaPartidaDTO(
        search_id=b.id,
        status=b.status,
        context=b.context,
        deck_id=b.deck_id,
        elo_snapshot=b.elo_snapshot,
        match_id=b.match_id,
        elapsed_seconds=round(b.elapsed_seconds, 2),
        bot_offer_available=resultado.bot_offer_available,
        bot_offer_in_seconds=resultado.bot_offer_in_seconds,
        state_version=b.state_version,
        created_at=b.created_at,
        last_seen_at=b.last_seen_at,
        warning_code=resultado.warning_code,
        warning_detail=resultado.warning_detail,
    )


def crear_router_emparejamiento(
    servicio: Callable[[], EmparejamientoService],
    requerir_jugador: Callable[..., Awaitable[Principal]],
) -> APIRouter:
    """Registra rutas de matchmaking, consulta/cancelación y Bot bajo /player."""
    router = APIRouter(prefix="/player", tags=["Matchmaking"])
    errores = respuestas_documentadas({
        401: "Sesión inválida o revocada",
        403: "Cuenta sin acceso de jugador o paquete sin abrir",
        404: "Deck o búsqueda no encontrada",
        409: "Conflicto de estado (partida activa, cubos insuficientes o búsqueda ya emparejada)",
        422: "Datos de entrada o deck inválidos",
        500: "Error interno",
        503: "Servicio temporalmente no disponible",
    })

    @router.post("/matchmaking", status_code=201, responses=errores)
    async def iniciar_busqueda(
        body: IniciarBusquedaRequest,
        request: Request,
        response: Response,
        principal: Principal = Depends(requerir_jugador),
    ) -> BusquedaPartidaDTO:
        """Ingresa a la cola con un deck de 12 cartas propias (idempotente en mismo contexto)."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        if body.deck_id is None or not body.deck_id.strip():
            raise problema(
                422,
                "deck_requerido",
                "Debes seleccionar un deck para buscar partida.",
            )

        try:
            resultado = await servicio().iniciar_busqueda(
                user_id=principal.id,
                deck_id=body.deck_id.strip(),
                context=body.context,
            )
        except PartidaActivaError as exc:
            raise problema(
                409,
                "partida_activa",
                str(exc),
                headers={"X-Match-ID": exc.match_id},
            ) from None
        except BusquedaVigenteOtroContextoError as exc:
            raise problema(409, "busqueda_vigente_otro_contexto", str(exc)) from None
        except DeckNoEncontradoBusquedaError as exc:
            raise problema(404, "deck_no_encontrado", str(exc)) from None
        except DeckInvalidoBusquedaError as exc:
            raise problema(422, "deck_invalido", str(exc)) from None
        except CubosInsuficientesError as exc:
            raise problema(409, "cubos_insuficientes", str(exc)) from None
        except EmparejamientoNoDisponibleError:
            raise problema(
                503,
                "emparejamiento_no_disponible",
                "El emparejamiento no está disponible temporalmente.",
            ) from None
        except Exception:
            logger.exception("Error inesperado iniciando búsqueda user=%s", principal.id)
            raise problema(500, "error_matchmaking", "No se pudo iniciar la búsqueda.") from None

        if not resultado.created:
            response.status_code = 200
        response.headers["ETag"] = resultado.etag
        response.headers["Cache-Control"] = "private, no-cache"
        return _a_dto(resultado)

    @router.get(
        "/matchmaking/current",
        response_model=BusquedaPartidaDTO,
        responses={
            204: {"description": "El jugador no tiene búsqueda activa"},
            304: {"description": "No modificado (ETag vigente)"},
            **errores,
        },
    )
    async def consultar_busqueda_actual(
        request: Request,
        response: Response,
        principal: Principal = Depends(requerir_jugador),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ) -> BusquedaPartidaDTO | Response:
        """Retorna la búsqueda SEARCHING activa del jugador, 204 o 304 si coincide ETag."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        try:
            resultado = await servicio().consultar_busqueda_actual(
                principal.id,
                if_none_match=if_none_match,
            )
        except EmparejamientoNoDisponibleError:
            raise problema(
                503,
                "emparejamiento_no_disponible",
                "No se pudo consultar tu búsqueda actual.",
            ) from None
        except Exception:
            logger.exception("Error consultando búsqueda actual user=%s", principal.id)
            raise problema(500, "error_matchmaking", "Error al consultar la búsqueda.") from None

        if resultado is None:
            return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
        if resultado.not_modified:
            return respuesta_no_modificada(resultado.etag, "private, no-cache")

        response.headers["ETag"] = resultado.etag
        response.headers["Cache-Control"] = "private, no-cache"
        return _a_dto(resultado)

    @router.get(
        "/matchmaking/{search_id}",
        response_model=BusquedaPartidaDTO,
        responses={304: {"description": "No modificado (ETag vigente)"}, **errores},
    )
    async def consultar_busqueda(
        search_id: str,
        request: Request,
        response: Response,
        principal: Principal = Depends(requerir_jugador),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ) -> BusquedaPartidaDTO | Response:
        """Consulta el estado de una búsqueda propia con heartbeat, ETag y oferta de Bot."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        try:
            resultado = await servicio().consultar_busqueda(
                principal.id,
                search_id,
                if_none_match=if_none_match,
            )
        except BusquedaNoEncontradaError:
            raise problema(404, "busqueda_no_encontrada", "La búsqueda no existe.") from None
        except EmparejamientoNoDisponibleError:
            raise problema(
                503,
                "emparejamiento_no_disponible",
                "No se pudo consultar la búsqueda.",
            ) from None
        except Exception:
            logger.exception("Error consultando búsqueda=%s user=%s", search_id, principal.id)
            raise problema(500, "error_matchmaking", "Error al consultar la búsqueda.") from None

        if resultado.not_modified:
            return respuesta_no_modificada(resultado.etag, "private, no-cache")

        response.headers["ETag"] = resultado.etag
        response.headers["Cache-Control"] = "private, no-cache"
        return _a_dto(resultado)

    @router.delete("/matchmaking/{search_id}", responses=errores)
    async def cancelar_busqueda(
        search_id: str,
        request: Request,
        response: Response,
        principal: Principal = Depends(requerir_jugador),
    ) -> BusquedaPartidaDTO:
        """Cancela atómicamente la búsqueda si sigue abierta, o informa match_id si emparejó."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        try:
            resultado = await servicio().cancelar_busqueda(principal.id, search_id)
        except BusquedaNoEncontradaError:
            raise problema(404, "busqueda_no_encontrada", "La búsqueda no existe.") from None
        except BusquedaYaEmparejadaError as exc:
            raise problema(
                409,
                "busqueda_ya_emparejada",
                str(exc),
                headers={"X-Match-ID": exc.match_id},
            ) from None
        except BusquedaTerminalError as exc:
            raise problema(409, f"busqueda_{exc.status.lower()}", str(exc)) from None
        except EmparejamientoNoDisponibleError:
            raise problema(
                503,
                "emparejamiento_no_disponible",
                "No se pudo cancelar la búsqueda.",
            ) from None
        except Exception:
            logger.exception("Error cancelando búsqueda=%s user=%s", search_id, principal.id)
            raise problema(500, "error_matchmaking", "Error al cancelar la búsqueda.") from None

        response.headers["ETag"] = resultado.etag
        response.headers["Cache-Control"] = "private, no-store"
        return _a_dto(resultado)

    @router.post("/matchmaking/{search_id}/accept-bot", responses=errores)
    async def aceptar_bot(
        search_id: str,
        request: Request,
        response: Response,
        principal: Principal = Depends(requerir_jugador),
    ) -> BusquedaPartidaDTO:
        """Acepta enfrentar al Bot tras >= 60 s en SEARCHING creando partida atómica."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        try:
            resultado = await servicio().aceptar_bot(principal.id, search_id)
        except BusquedaNoEncontradaError:
            raise problema(404, "busqueda_no_encontrada", "La búsqueda no existe.") from None
        except BusquedaYaEmparejadaError as exc:
            raise problema(
                409,
                "busqueda_ya_emparejada",
                str(exc),
                headers={"X-Match-ID": exc.match_id},
            ) from None
        except BusquedaTerminalError as exc:
            raise problema(409, f"busqueda_{exc.status.lower()}", str(exc)) from None
        except OfertaBotNoDisponibleError as exc:
            raise problema(409, "oferta_bot_no_disponible", str(exc)) from None
        except PartidaActivaError as exc:
            raise problema(
                409,
                "partida_activa",
                str(exc),
                headers={"X-Match-ID": exc.match_id},
            ) from None
        except DeckNoEncontradoBusquedaError as exc:
            raise problema(404, "deck_no_encontrado", str(exc)) from None
        except DeckInvalidoBusquedaError as exc:
            raise problema(422, "deck_invalido", str(exc)) from None
        except BotCatalogoInsuficienteError as exc:
            raise problema(409, "bot_catalogo_insuficiente", str(exc)) from None
        except EmparejamientoNoDisponibleError:
            raise problema(
                503,
                "emparejamiento_no_disponible",
                "No se pudo iniciar la partida contra el Bot.",
            ) from None
        except Exception:
            logger.exception("Error aceptando Bot búsqueda=%s user=%s", search_id, principal.id)
            raise problema(
                500,
                "error_matchmaking",
                "Error al iniciar partida contra el Bot.",
            ) from None

        response.headers["ETag"] = resultado.etag
        response.headers["Cache-Control"] = "private, no-cache"
        return _a_dto(resultado)

    return router
