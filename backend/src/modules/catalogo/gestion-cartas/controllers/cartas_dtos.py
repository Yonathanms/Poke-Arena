from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class TipoCarta(StrEnum):
    FUE = "FUE"
    AGU = "AGU"
    PLA = "PLA"
    ELE = "ELE"
    PSI = "PSI"
    LUC = "LUC"
    INC = "INC"


class RarezaCarta(StrEnum):
    COMUN = "COMUN"
    INFRECUENTE = "INFRECUENTE"
    RARA = "RARA"
    EPICA = "EPICA"
    LEGENDARIA = "LEGENDARIA"


class CartaResponseDTO(BaseModel):
    """Representación de una carta devuelta por la API."""
    id: str
    nombre: str
    codigo: str
    tipo: TipoCarta
    rareza: RarezaCarta
    coste_energia: int = Field(ge=0, le=10)
    puntos_vida: int = Field(gt=0)
    puntos_ataque: int = Field(ge=0)
    descripcion: str | None = None
    imagen_url: str | None = None
    imagen_miniatura_url: str | None = None
    precio: float | None = None
    activo: bool = True

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class CartaSearchQueryDTO(BaseModel):
    """Parámetros de consulta y filtrado para búsqueda de cartas."""
    q: str | None = Field(default=None, description="Término de búsqueda por nombre, código o descripción")
    tipo: TipoCarta | None = Field(default=None, description="Filtro opcional por tipo elemental")
    rareza: RarezaCarta | None = Field(default=None, description="Filtro opcional por rareza")
    limite: int = Field(default=15, ge=1, le=100, description="Cantidad máxima de cartas (defecto 15 para 3x5)")
    pagina: int = Field(default=1, ge=1, description="Número de página para paginado")


class CartaSearchResponseDTO(BaseModel):
    """Respuesta paginada del catálogo de cartas."""
    items: list[CartaResponseDTO]
    total: int
    pagina: int
    limite: int
    total_paginas: int
