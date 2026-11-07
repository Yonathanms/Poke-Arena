"""Representaciones puras; sin ORM, transporte ni flujo de creación de cartas."""

from dataclasses import dataclass, replace
from datetime import datetime
from re import fullmatch
from typing import Any


@dataclass(frozen=True, slots=True)
class Carta:
    """Estado de una carta; identidad y código vienen del caso de uso."""

    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability_id: str
    created_at: datetime
    image_id: str | None = None
    version: int = 1


@dataclass(frozen=True, slots=True)
class Habilidad:
    """Consulta de habilidad existente; params se conserva sin reinterpretar efectos."""

    id: str
    code: str
    name: str
    ability_type: str
    description: str
    params: dict[str, Any]
    has_effect: bool
    evolution_target_card_id: str | None


TIPOS_CARTA = frozenset(("FUE", "AGU", "PLA", "ELE", "PSI", "LUC"))
RAREZAS_CARTA = frozenset(("COMUN", "POCO_COMUN", "RARA", "LEGENDARIA"))


class DatosCartaInvalidos(ValueError):
    """Un campo de la carta incumple las reglas del catálogo."""


class CodigoAgotado(ValueError):
    """El contador ya alcanzó el último código asignable."""


@dataclass(frozen=True, slots=True)
class DatosCarta:
    """Atributos que el actor puede elegir al crear una carta."""

    nombre: str
    costo: int
    poder: int
    tipo: str
    rareza: str
    habilidad: str

    def normalizados(self) -> "DatosCarta":
        """Valida campos y recorta únicamente el nombre según la historia."""
        nombre = self.nombre.strip()
        if not 1 <= len(nombre) <= 100 or "\0" in nombre:
            raise DatosCartaInvalidos("Nombre inválido")
        if type(self.costo) is not int or not 0 <= self.costo <= 10:
            raise DatosCartaInvalidos("Costo fuera de rango")
        if type(self.poder) is not int or not -20 <= self.poder <= 20:
            raise DatosCartaInvalidos("Poder fuera de rango")
        if self.tipo not in TIPOS_CARTA or self.rareza not in RAREZAS_CARTA:
            raise DatosCartaInvalidos("Tipo o rareza inválidos")
        if not fullmatch(r"HAB-[0-9]{3}", self.habilidad):
            raise DatosCartaInvalidos("Código de habilidad inválido")
        return replace(self, nombre=nombre)


def siguiente_codigo(tipo: str, ultimo: int) -> str:
    """Formatea el siguiente valor del contador bloqueado por el llamador."""
    if ultimo >= 999:
        raise CodigoAgotado("El tipo agotó sus 999 códigos")
    return f"PKA-{tipo}-{ultimo + 1:03d}"
