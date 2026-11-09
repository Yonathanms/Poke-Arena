"""HTTP del paquete inicial y dependencia de acceso para funciones de jugador."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict

from src.modules.identidad.gestion_sesiones.domain.sesion_model import Principal
from src.shared.errores_rfc7807.respuestas import respuestas_documentadas
from src.shared.http_module import problema
from src.shared.seguridad_roles.bearer import token_plataforma

from ..domain.entrega_inicial_model import (
    EstadoPaquete,
    EstadoPaqueteInicial,
    EstadoProvisionInconsistente,
    JugadorNoElegible,
    PaquetePendiente,
    ProvisionNoDisponible,
    ResultadoProvision,
)
from ..services.entrega_inicial_service import EntregaInicial
from ..services.paquete_inicial_service import PaqueteInicial

logger = logging.getLogger(__name__)


class ConfirmarApertura(BaseModel):
    """La confirmación no recibe datos del jugador ni del premio."""

    model_config = ConfigDict(extra="forbid")


class CartaInicialDTO(BaseModel):
    """Identificador y datos públicos de una carta realmente asignada."""

    id: str
    code: str
    name: str


class PaqueteInicialDTO(BaseModel):
    """Estado HTTP del paquete del jugador autenticado."""

    state: EstadoPaquete
    received: bool
    opened: bool
    opened_at: datetime | None
    cards: list[CartaInicialDTO]


def _respuesta(estado: EstadoPaqueteInicial) -> PaqueteInicialDTO:
    return PaqueteInicialDTO(
        state=estado.estado,
        received=estado.estado is not EstadoPaquete.PENDING_CATALOG,
        opened=estado.estado is EstadoPaquete.COMPLETED,
        opened_at=estado.abierto_en,
        cards=[
            CartaInicialDTO(id=carta.id, code=carta.code, name=carta.name)
            for carta in estado.cartas
        ],
    )


async def provisionar_login(servicio: EntregaInicial, token: str) -> None:
    """Traduce la provisión al contrato HTTP del login sin exponer la sesión en errores."""
    try:
        resultado = await servicio.asegurar(token)
    except EstadoProvisionInconsistente:
        raise problema(
            409, "provision_inconsistente", "Estado de provisión inconsistente."
        ) from None
    except ProvisionNoDisponible:
        raise problema(503, "provision_no_disponible", "Reintenta iniciar sesión.") from None
    except Exception:
        logger.error("Error inesperado en la provisión de colección inicial")
        raise problema(500, "error_provision", "No se pudo completar la provisión.") from None
    if resultado is ResultadoProvision.NOT_ELIGIBLE:
        raise problema(403, "jugador_no_elegible", "Cuenta sin acceso a la provisión.")


def crear_router_paquete(
    servicio: Callable[[], PaqueteInicial],
    autenticar: Callable[..., Awaitable[Principal]],
) -> tuple[APIRouter, Callable[..., Awaitable[Principal]]]:
    """Devuelve las rutas del paquete y el guard para futuros endpoints exclusivos."""
    router = APIRouter(prefix="/player", tags=["Initial pack"])
    errores = respuestas_documentadas({
        401: "Sesión inválida o revocada",
        403: "Cuenta sin acceso de jugador",
        409: "Paquete pendiente o estado inconsistente",
        422: "Parámetros no admitidos",
        500: "Error interno",
        503: "Paquete no disponible",
    })

    async def jugador(principal: Principal = Depends(autenticar)) -> Principal:
        if principal.rol != "PLAYER":
            raise problema(403, "jugador_no_elegible", "Se requiere una cuenta de jugador.")
        return principal

    async def estado_http(
        operacion: Callable[[str], Awaitable[EstadoPaqueteInicial]], token: str,
    ) -> EstadoPaqueteInicial:
        try:
            return await operacion(token)
        except JugadorNoElegible:
            raise problema(403, "jugador_no_elegible", "Cuenta sin acceso de jugador.") from None
        except PaquetePendiente:
            raise problema(
                409, "paquete_pendiente", "La colección inicial sigue pendiente."
            ) from None
        except EstadoProvisionInconsistente:
            raise problema(
                409, "paquete_inconsistente", "El estado del paquete es inconsistente."
            ) from None
        except ProvisionNoDisponible:
            raise problema(503, "paquete_no_disponible", "El paquete no está disponible.") from None

    def sin_parametros(request: Request) -> None:
        if request.query_params:
            raise problema(422, "parametros_no_admitidos", "La ruta no acepta parámetros.")

    @router.get(
        "/initial-pack", responses=errores,
        description="Consulta el paquete. PENDING_CATALOG requiere reintentar el login.",
    )
    async def consultar(
        request: Request,
        response: Response,
        _: Principal = Depends(jugador),
        token: str = Depends(token_plataforma),
    ) -> PaqueteInicialDTO:
        """Lee el paquete sin cambiar inventario, saldo o apertura."""
        sin_parametros(request)
        response.headers["Cache-Control"] = "no-store"
        return _respuesta(await estado_http(servicio().consultar, token))

    @router.post("/initial-pack/open", responses=errores)
    async def abrir(
        request: Request,
        response: Response,
        body: ConfirmarApertura | None = None,
        _: Principal = Depends(jugador),
        token: str = Depends(token_plataforma),
    ) -> PaqueteInicialDTO:
        """Confirma la apertura una vez. Acepta una petición sin cuerpo o un objeto vacío."""
        sin_parametros(request)
        response.headers["Cache-Control"] = "no-store"
        return _respuesta(await estado_http(servicio().abrir, token))

    async def requerir_jugador_habilitado(
        principal: Principal = Depends(jugador),
        token: str = Depends(token_plataforma),
    ) -> Principal:
        """Restringe funciones exclusivas a un jugador con el paquete abierto."""
        estado = await estado_http(servicio().consultar, token)
        if estado.estado is not EstadoPaquete.COMPLETED:
            raise problema(403, "paquete_sin_abrir", "Abre el paquete inicial para continuar.")
        return principal

    return router, requerir_jugador_habilitado
