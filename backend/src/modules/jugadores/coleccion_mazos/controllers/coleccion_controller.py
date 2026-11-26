"""Endpoint HTTP GET /player/cards — colección de cartas del jugador."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.modules.identidad.gestion_sesiones.domain.sesion_model import Principal
from src.shared.errores_rfc7807.respuestas import respuestas_documentadas
from src.shared.http_module import problema

from ..services.paquete_inicial_service import ColeccionJugadorService

logger = logging.getLogger(__name__)


class PlayerCardDTO(BaseModel):
    id: str
    code: str
    name: str
    card_type: str
    rarity: str
    quantity: int


def crear_router_coleccion(
    servicio: Callable[[], ColeccionJugadorService],
    requerir_jugador: Callable[..., Awaitable[Principal]],
) -> APIRouter:
    """Compone la ruta de colección delegando el acceso de datos al caso de uso."""
    router = APIRouter(prefix="/player", tags=["Colección"])
    errores = respuestas_documentadas({
        401: "Sesión inválida o revocada",
        403: "Cuenta sin acceso de jugador o paquete sin abrir",
        500: "Error interno",
    })

    @router.get("/cards", responses=errores)
    async def listar_cartas_jugador(
        principal: Principal = Depends(requerir_jugador),
    ) -> list[PlayerCardDTO]:
        try:
            cartas = await servicio().listar_cartas(principal.id)
            return [
                PlayerCardDTO(
                    id=carta.id,
                    code=carta.code,
                    name=carta.name,
                    card_type=carta.card_type,
                    rarity=carta.rarity,
                    quantity=carta.quantity,
                )
                for carta in cartas
            ]
        except Exception:
            logger.exception("Error al listar cartas para user=%s", principal.id)
            raise problema(
                500, "error_listar_cartas", "No se pudo obtener tu colección."
            ) from None

    return router
