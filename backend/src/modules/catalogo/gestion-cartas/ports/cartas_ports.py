import importlib
from abc import ABC, abstractmethod

_dtos = importlib.import_module("src.modules.catalogo.gestion-cartas.controllers.cartas_dtos")
CartaResponseDTO = _dtos.CartaResponseDTO
CartaSearchQueryDTO = _dtos.CartaSearchQueryDTO
CartaSearchResponseDTO = _dtos.CartaSearchResponseDTO


class ICartaRepository(ABC):
    """Puerto de persistencia para operaciones de Catálogo de Cartas."""

    @abstractmethod
    async def buscar_cartas(self, params: CartaSearchQueryDTO) -> CartaSearchResponseDTO:
        """Busca cartas según los criterios especificados."""
        raise NotImplementedError

    @abstractmethod
    async def obtener_por_id_o_codigo(self, identificador: str) -> CartaResponseDTO | None:
        """Obtiene una carta específica por su UUID o código único."""
        raise NotImplementedError
