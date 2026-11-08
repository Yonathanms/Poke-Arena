import importlib
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.modules.catalogo.gestion_cartas_bridge import (
    CartaResponseDTO,
    CartaSearchQueryDTO,
    CartaSearchResponseDTO,
)

# Carga dinámica del Service y Adapter para compatibilidad con guión en carpetas
_adapter_module = importlib.import_module(
    "src.modules.catalogo.gestion-cartas.adapters.mongo_carta_repository"
)
MongoCartaRepository = _adapter_module.MongoCartaRepository

_service_module = importlib.import_module(
    "src.modules.catalogo.gestion-cartas.services.cartas_service"
)
CartasService = _service_module.CartasService

router = APIRouter(prefix="/content/cards", tags=["Catálogo - Cartas"])


def get_cartas_service() -> CartasService:
    """Inyección de dependencias para el servicio de cartas con adaptador NoSQL."""
    repository = MongoCartaRepository()
    return CartasService(repository=repository)


@router.get(
    "",
    response_model=CartaSearchResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Buscar y filtrar cartas del catálogo",
    description="Endpoint optimizado con MongoDB para búsquedas rápidas por texto, tipo, rareza y límite 15 (3x5).",
)
async def buscar_cartas(
    q: Annotated[str | None, Query(description="Nombre, código o texto descriptivo")] = None,
    tipo: Annotated[str | None, Query(description="Tipo elemental (ej. FUE, AGU, PLA)")] = None,
    rareza: Annotated[str | None, Query(description="Rareza (COMUN, INFRECUENTE, RARA, EPICA, LEGENDARIA)")] = None,
    limite: Annotated[int, Query(ge=1, le=100, description="Cartas por página (defecto 15)")] = 15,
    pagina: Annotated[int, Query(ge=1, description="Número de página")] = 1,
    service: CartasService = Depends(get_cartas_service),
) -> CartaSearchResponseDTO:
    """Mapea parámetros de URL al DTO de consulta y delega al CartasService."""
    search_params = CartaSearchQueryDTO(
        q=q,
        tipo=tipo,  # type: ignore[arg-type]
        rareza=rareza,  # type: ignore[arg-type]
        limite=limite,
        pagina=pagina,
    )
    return await service.buscar_cartas(search_params)


@router.get(
    "/{identificador}",
    response_model=CartaResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de carta por ID o Código",
)
async def obtener_detalle_carta(
    identificador: str,
    service: CartasService = Depends(get_cartas_service),
) -> CartaResponseDTO:
    carta = await service.obtener_detalle_carta(identificador)
    if not carta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ninguna carta con identificador '{identificador}'",
        )
    return carta
