from src.modules.catalogo.gestion_cartas_bridge import (
    ICartaRepository,
    CartaResponseDTO,
    CartaSearchQueryDTO,
    CartaSearchResponseDTO,
)


class CartasService:
    """Capa de lógica de negocio para operaciones sobre el catálogo de cartas."""

    def __init__(self, repository: ICartaRepository) -> None:
        self._repository = repository

    async def buscar_cartas(self, params: CartaSearchQueryDTO) -> CartaSearchResponseDTO:
        """Aplica validaciones de negocio en búsquedas y consulta al repositorio."""
        return await self._repository.buscar_cartas(params)

    async def obtener_detalle_carta(self, identificador: str) -> CartaResponseDTO | None:
        """Obtiene la ficha técnica de una carta por ID o Código."""
        return await self._repository.obtener_por_id_o_codigo(identificador)
