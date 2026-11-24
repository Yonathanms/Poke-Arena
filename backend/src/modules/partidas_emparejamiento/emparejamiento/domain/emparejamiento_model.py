"""Modelos, reglas de ventana Elo y excepciones puras de emparejamiento (US 2 y US 3)."""

from dataclasses import dataclass
from datetime import datetime


def calcular_ventana_elo(elapsed_seconds: float, max_elo_diff: int = 1000) -> int:
    """Devuelve la diferencia máxima de Elo permitida según el tiempo de espera."""
    if elapsed_seconds < 15.0:
        ventana = 100
    elif elapsed_seconds < 30.0:
        ventana = 250
    elif elapsed_seconds < 45.0:
        ventana = 500
    else:
        ventana = max_elo_diff
    return min(ventana, max_elo_diff)


def son_busquedas_compatibles(
    elo_a: int,
    elapsed_a: float,
    elo_b: int,
    elapsed_b: float,
    max_elo_diff: int = 1000,
) -> bool:
    """Dos búsquedas son compatibles si |elo_a - elo_b| <= max(ventana(A), ventana(B))."""
    tolerancia = max(
        calcular_ventana_elo(elapsed_a, max_elo_diff),
        calcular_ventana_elo(elapsed_b, max_elo_diff),
    )
    return abs(elo_a - elo_b) <= tolerancia


class EmparejamientoError(Exception):
    """Error base del dominio de emparejamiento."""


class PartidaActivaError(EmparejamientoError):
    """El jugador ya tiene una partida IN_PROGRESS y no puede buscar otra."""

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        super().__init__(f"Ya tienes una partida activa ({match_id}).")


class BusquedaVigenteOtroContextoError(EmparejamientoError):
    """El jugador ya tiene una búsqueda SEARCHING en otro contexto."""

    def __init__(self, search_id: str, context: str) -> None:
        self.search_id = search_id
        self.context = context
        super().__init__(
            f"Ya tienes una búsqueda abierta en contexto {context} ({search_id})."
        )


class BusquedaActivaDuplicadaError(EmparejamientoError):
    """Colisión concurrente sobre uq_match_searches_one_active_per_user."""


class DeckNoEncontradoBusquedaError(EmparejamientoError):
    """El deck indicado no existe o pertenece a otro jugador."""


class DeckInvalidoBusquedaError(EmparejamientoError):
    """El deck no tiene 12 cartas distintas o incluye cartas que el jugador ya no posee."""


class CubosInsuficientesError(EmparejamientoError):
    """El jugador no alcanza el mínimo de cubos requerido para clasificatoria."""

    def __init__(self, saldo_actual: int, requerido: int) -> None:
        self.saldo_actual = saldo_actual
        self.requerido = requerido
        super().__init__(
            f"Tienes {saldo_actual} cubos y necesitas al menos {requerido} para buscar "
            "partida clasificatoria. Compra cubos para continuar."
        )


class BusquedaNoEncontradaError(EmparejamientoError):
    """La búsqueda no existe o pertenece a otro jugador."""


class BusquedaYaEmparejadaError(EmparejamientoError):
    """La búsqueda ya encontró partida y no puede cancelarse ni reasignarse."""

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        super().__init__(f"La búsqueda ya encontró la partida {match_id}.")


class BusquedaTerminalError(EmparejamientoError):
    """La búsqueda ya se encuentra en un estado terminal (CANCELLED o EXPIRED)."""

    def __init__(self, status: str, mensaje: str | None = None) -> None:
        self.status = status
        super().__init__(mensaje or f"La búsqueda ya finalizó con estado {status}.")


class OfertaBotNoDisponibleError(EmparejamientoError):
    """Aún no se cumplen los segundos mínimos de espera para enfrentar al Bot."""

    def __init__(self, remaining_seconds: int) -> None:
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"La oferta contra el Bot estará disponible en {remaining_seconds} segundos."
        )


class BotCatalogoInsuficienteError(EmparejamientoError):
    """El catálogo no tiene al menos 12 cartas READY para conformar el deck del Bot."""


class EmparejamientoNoDisponibleError(EmparejamientoError):
    """Error transitorio de persistencia al gestionar el emparejamiento."""


@dataclass(frozen=True, slots=True)
class PerfilBusqueda:
    """Datos primarios del jugador leídos desde PostgreSQL."""

    elo: int
    cubes: int


@dataclass(frozen=True, slots=True)
class BusquedaPartida:
    """Snapshot de una fila match_searches con tiempos calculados en reloj SQL."""

    id: str
    user_id: str
    deck_id: str | None
    context: str
    elo_snapshot: int
    status: str
    match_id: str | None
    state_version: int
    created_at: datetime
    last_seen_at: datetime
    elapsed_seconds: float
    inactive_seconds: float


@dataclass(frozen=True, slots=True)
class ResultadoBusqueda:
    """Resultado de operación/consulta de búsqueda con ETag y posible aviso de savepoint."""

    busqueda: BusquedaPartida | None
    created: bool
    not_modified: bool
    etag: str
    bot_offer_available: bool
    bot_offer_in_seconds: int
    warning_code: str | None = None
    warning_detail: str | None = None
