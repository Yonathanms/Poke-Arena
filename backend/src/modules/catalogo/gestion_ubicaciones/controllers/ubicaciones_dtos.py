"""DTOs de entrada y respuesta para el endpoint de ubicaciones."""
from typing import Any

from pydantic import BaseModel


class UbicacionResponseDTO(BaseModel):
    id: str
    nombre: str
    descripcion: str
    card_limit: int
    energia_tipo: str
    energia_valor: int
    efecto_tipo: str
    efecto_params: dict[str, Any]
    url_grande: str
    url_tablero: str
    created_at: str | None
