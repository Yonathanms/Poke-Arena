"""Contratos de coordinación durable para Crear Carta."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..domain.carta_model import Carta
from ..domain.imagen_model import ImagenAlmacenada
from .cartas_ports import CartasRepositoryPort, ErrorPersistencia

COMPENSACION_PENDIENTE = "compensacion_pendiente"


@dataclass(frozen=True, slots=True)
class ClaveCreacion:
    """Alcance de idempotencia reutilizado de la operación histórica."""

    actor: str
    clave: str
    operacion: str = "POST:/api/v1/content/cards"


@dataclass(frozen=True, slots=True)
class RegistroCreacion:
    """Reserva leída del primario junto con su resultado o imagen pendiente."""

    id: str
    recurso: str | None
    huella: str
    estado_respuesta: int | None
    respuesta: object
    imagen: ImagenAlmacenada | None
    estado_imagen: str | None
    compensacion_pendiente: bool = False
    codigo_confirmado: str | None = None


class CommitIncierto(ErrorPersistencia):
    """La infraestructura no confirmó si el commit se hizo durable."""


class ClaveOcupada(Exception):
    """Otra sesión posee temporalmente el lock de esta clave."""


class TransaccionCreacionPort(Protocol):
    """Operaciones SQL con una sesión y una transacción ya abiertas."""

    @property
    def cartas(self) -> CartasRepositoryPort:
        """Repositorio existente, enlazado a esta transacción."""
        ...

    async def obtener(self, clave: ClaveCreacion) -> RegistroCreacion | None:
        """Lee y bloquea el registro idempotente si existe."""
        ...

    async def reservar(
        self,
        clave: ClaveCreacion,
        operacion_id: str,
        huella: str,
        imagen: ImagenAlmacenada,
        ahora: datetime,
    ) -> None:
        """Crea el registro pendiente y sus referencias de imagen en el mismo commit."""
        ...

    async def registrar_intento(self, operacion_id: str, ahora: datetime) -> None:
        """Registra el intento antes de comenzar I/O de medios."""
        ...

    async def registrar_fallo(self, operacion_id: str, error: str, ahora: datetime) -> None:
        """Conserva la reserva y un diagnóstico sanitizado en RETRY_PENDING."""
        ...

    async def puede_compensar(self, operacion_id: str, imagen: ImagenAlmacenada) -> bool:
        """Comprueba ausencia de cartas y de otras filas con referencias compartidas."""
        ...

    async def terminar_compensacion(self, operacion_id: str, ahora: datetime) -> None:
        """Retira el bloqueo durable después de confirmar ambos borrados."""
        ...

    async def marcar_lista(self, operacion_id: str, ahora: datetime) -> None:
        """Marca READY la reserva ya verificada por el servicio."""
        ...

    async def agregar_evento(self, carta: Carta, payload: dict[str, str | int]) -> None:
        """Inserta el sobre CardCreated existente en la transacción de la carta."""
        ...

    async def confirmar(self, operacion_id: str, respuesta: dict[str, str | int]) -> None:
        """Persiste el par de respuesta idempotente junto con la carta."""
        ...


class OperacionCreacionPort(Protocol):
    """Sesión exclusiva de la operación, con transacciones SQL cortas."""

    def transaccion(self) -> AbstractAsyncContextManager[TransaccionCreacionPort]:
        """Abre una transacción que confirma al salir y distingue commit incierto."""
        ...


class CoordinacionCreacionPort(Protocol):
    """Exclusión persistente por alcance de idempotencia."""

    def exclusiva(self, clave: ClaveCreacion) -> AbstractAsyncContextManager[OperacionCreacionPort]:
        """Adquiere la exclusión o lanza ClaveOcupada."""
        ...
