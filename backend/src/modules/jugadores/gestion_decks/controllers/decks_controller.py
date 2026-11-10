"""Endpoints HTTP para creación y listado de decks del jugador."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from src.modules.identidad.gestion_sesiones.domain.sesion_model import Principal
from src.shared.errores_rfc7807.respuestas import respuestas_documentadas
from src.shared.http_module import problema

from ..domain.deck_model import (
    DeckCartasNoPertenecen,
    DeckCartasRepetidas,
    DeckEnCurso,
    DeckNoEncontrado,
    DeckNombreOcupado,
    DeckTamanoInvalido,
)
from ..services.decks_service import DecksService
from .decks_dtos import CrearDeckRequest, DeckDetalleDTO, DeckResumenDTO, EditarDeckRequest

logger = logging.getLogger(__name__)


def crear_router_decks(
    servicio: Callable[[], DecksService],
    requerir_jugador: Callable[..., Awaitable[Principal]],
) -> APIRouter:
    router = APIRouter(prefix="/player", tags=["Decks"])
    errores = respuestas_documentadas({
        400: "Solicitud inválida",
        401: "Sesión inválida o revocada",
        403: "Cuenta sin acceso de jugador o paquete sin abrir",
        409: "Nombre de deck ya utilizado o solicitud en curso",
        422: "Datos de entrada inválidos",
        500: "Error interno",
    })

    @router.post("/decks", status_code=201, responses=errores)
    async def crear_deck(
        body: CrearDeckRequest,
        request: Request,
        principal: Principal = Depends(requerir_jugador),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> DeckResumenDTO:
        """Crea un deck de 12 cartas. Requiere Idempotency-Key."""
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        if not idempotency_key or not idempotency_key.strip():
            raise problema(400, "idempotency_key_requerida", "Se requiere el header Idempotency-Key.")

        try:
            deck = await servicio().crear_deck(
                user_id=principal.id,
                name=body.name,
                card_ids=body.card_ids,
                idempotency_key=idempotency_key.strip(),
            )
        except DeckTamanoInvalido as exc:
            raise problema(
                422,
                "deck_tamano_invalido",
                f"Se requieren exactamente 12 cartas; se recibieron {exc.recibidas}.",
            ) from None
        except DeckCartasRepetidas as exc:
            raise problema(
                422,
                "deck_cartas_repetidas",
                f"card_ids contiene duplicados: {exc.repetidas}.",
            ) from None
        except DeckCartasNoPertenecen as exc:
            raise problema(
                422,
                "deck_cartas_no_pertenecen",
                f"Las siguientes cartas no están en tu colección: {exc.faltantes}.",
            ) from None
        except DeckNombreOcupado:
            raise problema(
                409,
                "deck_nombre_ocupado",
                f"Ya tienes un deck llamado {body.name!r}.",
            ) from None
        except DeckEnCurso:
            raise problema(
                409,
                "deck_en_curso",
                "Otra solicitud con la misma Idempotency-Key está en progreso.",
            ) from None
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error inesperado al crear deck para user=%s", principal.id)
            raise problema(500, "error_crear_deck", "No se pudo crear el deck.") from None

        return DeckResumenDTO(
            id=deck.id,
            name=deck.name,
            card_count=len(deck.card_ids),
            created_at=deck.created_at,
        )

    @router.get("/decks", responses=errores)
    async def listar_decks(
        request: Request,
        principal: Principal = Depends(requerir_jugador),
    ) -> list[DeckResumenDTO]:
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")
        try:
            decks = await servicio().listar_decks(principal.id)
        except Exception:
            logger.exception("Error al listar decks para user=%s", principal.id)
            raise problema(500, "error_listar_decks", "No se pudieron obtener los decks.") from None

        return [
            DeckResumenDTO(id=d.id, name=d.name, card_count=d.card_count, created_at=d.created_at)
            for d in decks
        ]

    @router.get("/decks/{deck_id}", responses=errores)
    async def obtener_deck(
        deck_id: str,
        principal: Principal = Depends(requerir_jugador),
    ) -> DeckDetalleDTO:
        try:
            deck = await servicio().obtener_deck(principal.id, deck_id)
        except DeckNoEncontrado:
            raise problema(404, "deck_no_encontrado", "El deck no existe.") from None
        except Exception:
            logger.exception("Error al obtener deck %s para user=%s", deck_id, principal.id)
            raise problema(500, "error_obtener_deck", "No se pudo obtener el deck.") from None

        return DeckDetalleDTO(
            id=deck.id, name=deck.name,
            card_ids=list(deck.card_ids), created_at=deck.created_at,
        )

    @router.put("/decks/{deck_id}", responses=errores)
    async def actualizar_deck(
        deck_id: str,
        body: EditarDeckRequest,
        principal: Principal = Depends(requerir_jugador),
    ) -> DeckResumenDTO:
        try:
            deck = await servicio().actualizar_deck(
                principal.id, deck_id, body.name, body.card_ids
            )
        except DeckNoEncontrado:
            raise problema(404, "deck_no_encontrado", "El deck no existe.") from None
        except DeckTamanoInvalido as exc:
            raise problema(422, "deck_tamano_invalido",
                           f"Se requieren exactamente 12 cartas; se recibieron {exc.recibidas}.") from None
        except DeckCartasRepetidas as exc:
            raise problema(422, "deck_cartas_repetidas",
                           f"card_ids contiene duplicados: {exc.repetidas}.") from None
        except DeckCartasNoPertenecen as exc:
            raise problema(422, "deck_cartas_no_pertenecen",
                           f"Las siguientes cartas no están en tu colección: {exc.faltantes}.") from None
        except DeckNombreOcupado:
            raise problema(409, "deck_nombre_ocupado",
                           f"Ya tienes un deck llamado {body.name!r}.") from None
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error al actualizar deck %s para user=%s", deck_id, principal.id)
            raise problema(500, "error_actualizar_deck", "No se pudo actualizar el deck.") from None

        return DeckResumenDTO(
            id=deck.id, name=deck.name,
            card_count=len(deck.card_ids), created_at=deck.created_at,
        )

    @router.delete("/decks/{deck_id}", status_code=204, responses=errores)
    async def eliminar_deck(
        deck_id: str,
        principal: Principal = Depends(requerir_jugador),
    ) -> None:
        try:
            await servicio().eliminar_deck(principal.id, deck_id)
        except DeckNoEncontrado:
            raise problema(404, "deck_no_encontrado", "El deck no existe.") from None
        except Exception:
            logger.exception("Error al eliminar deck %s para user=%s", deck_id, principal.id)
            raise problema(500, "error_eliminar_deck", "No se pudo eliminar el deck.") from None

    return router
