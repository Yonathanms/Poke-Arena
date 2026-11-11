"""Contratos de persistencia; sin SQL, política HTTP ni asignación de códigos."""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Protocol

from ..domain.carta_model import Carta, Habilidad


class TipoErrorPersistencia(StrEnum):
    """Categorías técnicas traducibles posteriormente a errores del dominio."""

    DUPLICADO = "duplicado"
    REFERENCIA = "referencia"
    RESTRICCION = "restriccion"
    OPERACION = "operacion"


class ErrorPersistencia(Exception):
    """Fallo sin SQL ni parámetros; tras una escritura fallida hay que revertir."""

    def __init__(self, tipo: TipoErrorPersistencia, restriccion: str | None = None) -> None:
        """Conserva categoría y nombre de constraint, nunca detalles del driver."""
        self.tipo = tipo
        self.restriccion = restriccion
        super().__init__(f"Error de persistencia: {tipo.value}")


class CartasRepositoryPort(Protocol):
    """Opera en transacción del llamador; nunca commit/rollback/close."""

    async def buscar_por_id(self, carta_id: str) -> Carta | None:
        """Devuelve estado puro o None; no carga binarios ni relaciones implícitas."""
        ...

    async def buscar_por_codigo(self, codigo: str) -> Carta | None:
        """Consulta un código público existente sin reservar consecutivos."""
        ...

    async def buscar_habilidad_por_codigo(self, codigo: str) -> Habilidad | None:
        """Consulta habilidades existentes sin crear ni modificar efectos."""
        ...

    async def agregar(self, carta: Carta) -> None:
        """Inserta sin confirmar; constraints fallidos producen ErrorPersistencia."""
        ...

    async def bloquear_contador(self, tipo: str) -> int | None:
        """Lee con bloqueo hasta terminar la transacción; no incrementa ni crea filas."""
        ...

    async def actualizar_contador(self, tipo: str, valor: int) -> None:
        """Persiste un valor tras bloquear la fila en la misma transacción."""
        ...

    async def ruta_evolucion(self, destino: str) -> tuple[str, ...]:
        """Lee la cadena en un snapshot SQL. Una repetición indica un ciclo."""
        ...

    async def listar_tipos(self) -> list[tuple[str, str, str | None]]:
        """Lee códigos, nombres y descripciones de tipos existentes."""
        ...

    async def listar_rarezas(self) -> list[tuple[str, str]]:
        """Lee códigos y nombres de rarezas existentes."""
        ...


# ------------------------------------------------------------------------------
# Puerto para Búsqueda y Consulta NoSQL de Cartas
# ------------------------------------------------------------------------------

class ICartaRepository(ABC):
    """Puerto de persistencia para operaciones de consulta y búsqueda en Catálogo."""

    @abstractmethod
    async def buscar_cartas(self, params: object) -> object:
        """Busca cartas según los criterios especificados."""
        raise NotImplementedError

    @abstractmethod
    async def obtener_por_id_o_codigo(self, identificador: str) -> object | None:
        """Obtiene una carta específica por su UUID o código único."""
        raise NotImplementedError


class IInventarioJugadorPort(ABC):
    """Puerto de persistencia para consultar el inventario de cartas del jugador (player_cards)."""

    @abstractmethod
    async def obtener_cantidades_por_usuario(self, user_id: str) -> dict[str, int]:
        """Devuelve un mapa {card_id: quantity} con las cartas que posee el jugador."""
        raise NotImplementedError
