"""Invariantes, entidades y máquina de estados de la colección inicial."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from src.shared.maquina_estados import MaquinaEstados

INITIAL_CARD_COUNT = 15
INITIAL_CUBES = 1_000
INITIAL_COLLECTION = "INITIAL_COLLECTION"


class ResultadoProvision(StrEnum):
    """Resultados esperados que no necesitan datos del inventario."""

    GRANTED = "GRANTED"
    ALREADY_GRANTED = "ALREADY_GRANTED"
    INSUFFICIENT_CATALOG = "INSUFFICIENT_CATALOG"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


@dataclass(frozen=True, slots=True)
class PerfilProvision:
    """Estado del perfil leído bajo bloqueo compartido o exclusivo."""

    cubes: int
    recibido: bool
    abierto_en: datetime | None


class EstadoProvisionInconsistente(Exception):
    """El perfil falta o contiene beneficios incompatibles con una primera entrega."""


class ProvisionNoDisponible(Exception):
    """Falló la persistencia de la provisión."""


class EstadoPaquete(StrEnum):
    """Estados observables del paquete inicial."""

    PENDING_CATALOG = "PENDING_CATALOG"
    READY_TO_OPEN = "READY_TO_OPEN"
    COMPLETED = "COMPLETED"


class EventoPaquete(StrEnum):
    """Eventos válidos del ciclo de vida del paquete inicial."""

    PROVISIONAR = "PROVISIONAR"
    ABRIR = "ABRIR"


MAQUINA_ESTADOS_PAQUETE: MaquinaEstados[EstadoPaquete, EventoPaquete] = MaquinaEstados({
    (EstadoPaquete.PENDING_CATALOG, EventoPaquete.PROVISIONAR): EstadoPaquete.READY_TO_OPEN,
    (EstadoPaquete.READY_TO_OPEN, EventoPaquete.ABRIR): EstadoPaquete.COMPLETED,
    (EstadoPaquete.COMPLETED, EventoPaquete.ABRIR): EstadoPaquete.COMPLETED,
})


@dataclass(frozen=True, slots=True)
class CartaPaquete:
    """Carta realmente asignada al perfil, con sus datos públicos de catálogo."""

    id: str
    code: str
    name: str
    quantity: int
    card_type: str = "FUE"
    rarity: str = "COMUN"
    cost: int = 0
    power: int = 0
    ability_code: str = "HAB-000"
    ability_name: str = "Sin Habilidad"


@dataclass(frozen=True, slots=True)
class CartaColeccion:
    """Carta perteneciente a la colección del jugador."""

    id: str
    code: str
    name: str
    card_type: str
    rarity: str
    quantity: int


@dataclass(frozen=True, slots=True)
class EstadoPaqueteInicial:
    """Estado y contenido visible del paquete para su jugador."""

    estado: EstadoPaquete
    abierto_en: datetime | None = None
    cartas: tuple[CartaPaquete, ...] = ()


class JugadorNoElegible(Exception):
    """Identidad no autorizada para operaciones exclusivas de jugador."""


class PaquetePendiente(Exception):
    """La operación requiere beneficios o apertura que todavía faltan."""
