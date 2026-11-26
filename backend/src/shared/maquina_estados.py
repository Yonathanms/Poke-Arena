"""Máquina de estados finitos dirigida por tabla (Table-Driven FSM).

Componente transversal puro y sin dependencias de infraestructura. Garantiza que
toda transición de estado esté declarada explícitamente y rechaza las prohibidas
(RNF-INT-05, RNF-ARQ-01).
"""

from collections.abc import Mapping
from types import MappingProxyType


class TransicionInvalida(Exception):
    """Se intentó aplicar un evento no permitido desde el estado actual."""

    def __init__(
        self,
        estado_actual: object,
        evento: object,
        eventos_permitidos: frozenset[object],
    ) -> None:
        self.estado_actual = estado_actual
        self.evento = evento
        self.eventos_permitidos = eventos_permitidos
        super().__init__(
            f"Transición prohibida: estado={estado_actual!r}, evento={evento!r}"
        )


class MaquinaEstados[Estado, Evento]:
    """Máquina de estados inmutable basada en una tabla explícita de transiciones."""

    def __init__(self, transiciones: Mapping[tuple[Estado, Evento], Estado]) -> None:
        self._transiciones: Mapping[tuple[Estado, Evento], Estado] = MappingProxyType(
            dict(transiciones)
        )

    def transicionar(self, estado_actual: Estado, evento: Evento) -> Estado:
        """Devuelve el siguiente estado válido o lanza TransicionInvalida."""
        siguiente = self._transiciones.get((estado_actual, evento))
        if siguiente is None:
            raise TransicionInvalida(
                estado_actual=estado_actual,
                evento=evento,
                eventos_permitidos=self.eventos_disponibles(estado_actual),
            )
        return siguiente

    def puede_transicionar(self, estado_actual: Estado, evento: Evento) -> bool:
        """Indica si el par (estado_actual, evento) es una transición permitida."""
        return (estado_actual, evento) in self._transiciones

    def eventos_disponibles(self, estado_actual: Estado) -> frozenset[Evento]:
        """Retorna los eventos válidos desde el estado indicado."""
        return frozenset(
            evento for estado, evento in self._transiciones if estado == estado_actual
        )

    @property
    def tabla(self) -> Mapping[tuple[Estado, Evento], Estado]:
        """Expone una vista de solo lectura de la tabla de transiciones."""
        return self._transiciones
