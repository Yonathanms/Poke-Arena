"""Esquemas HTTP de Crear y Buscar Carta, separados del servicio y del dominio."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..services.cartas_service import ResultadoCrearCarta


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


# ------------------------------------------------------------------------------
# DTOs para Creación de Cartas (1D / 1E)
# ------------------------------------------------------------------------------

class CamposCrearCarta(BaseModel):
    """Campos textuales multipart. Las invariantes de negocio quedan en 1D."""

    model_config = ConfigDict(extra="forbid")

    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability_code: str


class CartaCreada(BaseModel):
    """Resultado confirmado del mismo recurso para creación y replay."""

    id: str
    code: str
    operation_id: str
    image_id: str
    image_status: Literal["READY"]

    @classmethod
    def desde_resultado(cls, resultado: ResultadoCrearCarta) -> "CartaCreada":
        """Proyecta el resultado tipado de 1D sin exponer referencias GridFS."""
        return cls(
            id=resultado.carta_id,
            code=resultado.codigo,
            operation_id=resultado.operacion_id,
            image_id=resultado.imagen_id,
            image_status=resultado.estado_imagen,
        )


def esquema_multipart() -> dict[str, object]:
    """Describe explícitamente el cuerpo, leído con un límite antes de parsear."""
    esquema = CamposCrearCarta.model_json_schema()
    esquema["properties"]["image"] = {
        "type": "string",
        "format": "binary",
        "description": "Original PNG, JPEG o WebP. Máximo 5 000 000 bytes.",
    }
    esquema["required"].append("image")
    return {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": esquema,
                "example": {
                    "name": "Guardiana",
                    "cost": 2,
                    "power": 5,
                    "card_type": "AGU",
                    "rarity": "RARA",
                    "ability_code": "HAB-000",
                    "image": "(binario)",
                },
            }
        },
    }


class HabilidadSeleccionable(BaseModel):
    """Identificador y etiqueta de una habilidad existente para el formulario."""

    code: str
    name: str


# ------------------------------------------------------------------------------
# DTOs para Consulta y Búsqueda de Cartas (Catálogo / Jugadores)
# ------------------------------------------------------------------------------

class CartaResponseDTO(BaseModel):
    """Representación de una carta devuelta por la API para búsqueda y visualización."""

    id: str
    name: str = Field(default="", validation_alias=AliasChoices("name", "nombre"))
    code: str = Field(default="", validation_alias=AliasChoices("code", "codigo"))
    type: str = Field(default="FUE", validation_alias=AliasChoices("type", "tipo", "card_type"))
    rarity: str = Field(default="COMUN", validation_alias=AliasChoices("rarity", "rareza"))
    cost: int = Field(default=0, validation_alias=AliasChoices("cost", "coste_energia"), ge=0, le=10)
    power: int = Field(default=0, validation_alias=AliasChoices("power", "puntos_ataque"))
    hp: int = Field(default=100, validation_alias=AliasChoices("hp", "puntos_vida"))
    imageUrl: str | None = Field(default=None, validation_alias=AliasChoices("imageUrl", "imagen_url"))
    thumbnailUrl: str | None = Field(default=None, validation_alias=AliasChoices("thumbnailUrl", "imagen_miniatura_url"))
    description: str | None = Field(default=None, validation_alias=AliasChoices("description", "descripcion"))
    price: float | None = None
    activo: bool = True
    ability_code: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @property
    def nombre(self) -> str:
        return self.name

    @property
    def codigo(self) -> str:
        return self.code

    @property
    def tipo(self) -> str:
        return self.type

    @property
    def rareza(self) -> str:
        return self.rarity


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
