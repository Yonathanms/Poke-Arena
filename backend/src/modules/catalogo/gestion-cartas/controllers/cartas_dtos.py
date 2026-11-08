"""Esquemas HTTP de Crear Carta, separados del servicio y del dominio."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..services.cartas_service import ResultadoCrearCarta


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
