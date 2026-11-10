"""Modelos puros del dominio de Decks. Sin imports de SQLAlchemy, FastAPI ni I/O."""

from dataclasses import dataclass
from datetime import datetime

MAX_DECK_SIZE = 12


@dataclass(frozen=True, slots=True)
class DeckResumen:
    """Datos públicos del deck para listados."""

    id: str
    name: str
    card_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Deck:
    """Deck completo incluyendo sus cartas."""

    id: str
    user_id: str
    name: str
    card_ids: frozenset[str]
    created_at: datetime


class DeckTamanoInvalido(Exception):
    """El deck no tiene exactamente MAX_DECK_SIZE cartas."""

    def __init__(self, recibidas: int) -> None:
        self.recibidas = recibidas
        super().__init__(f"Tamaño inválido: {recibidas}")


class DeckCartasRepetidas(Exception):
    """El input del cliente incluye card_ids duplicados."""

    def __init__(self, repetidas: list[str]) -> None:
        self.repetidas = repetidas
        super().__init__(f"Cartas repetidas: {repetidas}")


class DeckCartasNoPertenecen(Exception):
    """Una o más cartas no están en la colección del jugador."""

    def __init__(self, faltantes: list[str]) -> None:
        self.faltantes = faltantes
        super().__init__(f"Cartas no poseídas: {faltantes}")


class DeckNombreOcupado(Exception):
    """El jugador ya tiene un deck con ese nombre."""

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre
        super().__init__(f"Nombre ocupado: {nombre!r}")


class DeckNoEncontrado(Exception):
    """El deck no existe o no pertenece al jugador."""


class DeckEnCurso(Exception):
    """Otra solicitud con la misma Idempotency-Key está en progreso."""
