import importlib

# Carga de DTOs
_dtos = importlib.import_module("src.modules.catalogo.gestion-cartas.controllers.cartas_dtos")
CartaResponseDTO = _dtos.CartaResponseDTO
CartaSearchQueryDTO = _dtos.CartaSearchQueryDTO
CartaSearchResponseDTO = _dtos.CartaSearchResponseDTO

# Carga de Puertos
_ports = importlib.import_module("src.modules.catalogo.gestion-cartas.ports.cartas_ports")
ICartaRepository = _ports.ICartaRepository

__all__ = [
    "CartaResponseDTO",
    "CartaSearchQueryDTO",
    "CartaSearchResponseDTO",
    "ICartaRepository",
]
