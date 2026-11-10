"""Endpoint GET /player/cards — colección de cartas del jugador."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from src.modules.identidad.gestion_sesiones.domain.sesion_model import Principal
from src.shared.errores_rfc7807.respuestas import respuestas_documentadas
from src.shared.http_module import problema

logger = logging.getLogger(__name__)

_SQL = text("""
    SELECT c.id, c.code, c.name, c.card_type, c.rarity, pc.quantity
    FROM player_cards pc
    JOIN catalog_cards c ON c.id = pc.card_id
    WHERE pc.user_id = :user_id
    ORDER BY c.card_type, c.name
""")


class PlayerCardDTO(BaseModel):
    id: str
    code: str
    name: str
    card_type: str
    rarity: str
    quantity: int


def crear_router_coleccion(
    requerir_jugador: Callable[..., Awaitable[Principal]],
) -> APIRouter:
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
        from src.database.postgresql.connection import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as sesion:
                filas = await sesion.execute(_SQL, {"user_id": principal.id})
                return [
                    PlayerCardDTO(
                        id=f[0], code=f[1], name=f[2],
                        card_type=f[3], rarity=f[4], quantity=f[5],
                    )
                    for f in filas
                ]
        except Exception:
            logger.exception("Error al listar cartas para user=%s", principal.id)
            raise problema(500, "error_listar_cartas", "No se pudo obtener tu colección.") from None

    return router
