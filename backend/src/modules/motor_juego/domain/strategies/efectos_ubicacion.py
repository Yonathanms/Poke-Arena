"""Estrategias extensibles de elegibilidad y energía para ubicaciones (RNF-ARQ-02)."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from ..modelos_partida import TURNOS_PARTIDA, UbicacionSnapshot


@runtime_checkable
class EstrategiaUbicacion(Protocol):
    """Contrato puro para evaluar restricciones de juego de una ubicación."""

    def permite_jugar_en_turno(self, ubicacion: UbicacionSnapshot, turno: int) -> bool:
        """Indica si el efecto de la ubicación permite jugar cartas en el turno dado."""
        ...

    def permite_jugar_en_algun_turno(
        self, ubicacion: UbicacionSnapshot, turnos_partida: frozenset[int]
    ) -> bool:
        """Indica si existe al menos un turno de la partida donde la ubicación sea jugable."""
        ...


@runtime_checkable
class EstrategiaEnergiaUbicacion(Protocol):
    """Contrato puro para calcular el bono de energía otorgado por una ubicación."""

    def calcular_energia_extra(
        self, ubicacion: UbicacionSnapshot, cartas_propias_en_ubicacion: int
    ) -> int:
        """Retorna la energía extra aportada al inicio del turno."""
        ...


class EstrategiaEfectoLibre:
    """Efectos que no bloquean turnos de juego (bonificaciones, modificadores, etc.)."""

    def permite_jugar_en_turno(self, ubicacion: UbicacionSnapshot, turno: int) -> bool:
        return True

    def permite_jugar_en_algun_turno(
        self, ubicacion: UbicacionSnapshot, turnos_partida: frozenset[int]
    ) -> bool:
        return bool(turnos_partida)


class EstrategiaRestriccionTurno:
    """Efecto que prohíbe jugar cartas durante la lista configurada de turnos."""

    def _turnos_bloqueados(self, ubicacion: UbicacionSnapshot) -> frozenset[int]:
        raw = ubicacion.efecto_params.get("turnos", ())
        if not isinstance(raw, (list, tuple, set, frozenset)):
            return frozenset()
        return frozenset(t for t in raw if isinstance(t, int) and not isinstance(t, bool))

    def permite_jugar_en_turno(self, ubicacion: UbicacionSnapshot, turno: int) -> bool:
        return turno not in self._turnos_bloqueados(ubicacion)

    def permite_jugar_en_algun_turno(
        self, ubicacion: UbicacionSnapshot, turnos_partida: frozenset[int]
    ) -> bool:
        bloqueados = self._turnos_bloqueados(ubicacion)
        return bool(turnos_partida - bloqueados)


class EstrategiaEnergiaFija:
    """Otorga un monto fijo de energía al inicio de cada turno."""

    def calcular_energia_extra(
        self, ubicacion: UbicacionSnapshot, cartas_propias_en_ubicacion: int
    ) -> int:
        return ubicacion.energia_valor


class EstrategiaEnergiaPorCartas:
    """Otorga energía proporcional al número de cartas propias en la ubicación."""

    def calcular_energia_extra(
        self, ubicacion: UbicacionSnapshot, cartas_propias_en_ubicacion: int
    ) -> int:
        return ubicacion.energia_valor * cartas_propias_en_ubicacion


class RegistroEstrategiasUbicacion:
    """Registro inmutable de estrategias de efectos y energía extensible por composición."""

    def __init__(
        self,
        efectos: Mapping[str, EstrategiaUbicacion],
        energias: Mapping[str, EstrategiaEnergiaUbicacion],
        efecto_por_defecto: EstrategiaUbicacion | None = None,
    ) -> None:
        self._efectos: Mapping[str, EstrategiaUbicacion] = MappingProxyType(dict(efectos))
        self._energias: Mapping[str, EstrategiaEnergiaUbicacion] = MappingProxyType(dict(energias))
        self._efecto_por_defecto: EstrategiaUbicacion = (
            efecto_por_defecto if efecto_por_defecto is not None else EstrategiaEfectoLibre()
        )

    def con_efecto(
        self, efecto_tipo: str, estrategia: EstrategiaUbicacion
    ) -> "RegistroEstrategiasUbicacion":
        """Devuelve un nuevo registro añadiendo o reemplazando la estrategia del efecto."""
        return RegistroEstrategiasUbicacion(
            {**self._efectos, efecto_tipo: estrategia},
            self._energias,
            self._efecto_por_defecto,
        )

    def con_energia(
        self, energia_tipo: str, estrategia: EstrategiaEnergiaUbicacion
    ) -> "RegistroEstrategiasUbicacion":
        """Devuelve un nuevo registro añadiendo o reemplazando la estrategia de energía."""
        return RegistroEstrategiasUbicacion(
            self._efectos,
            {**self._energias, energia_tipo: estrategia},
            self._efecto_por_defecto,
        )

    def obtener_efecto(self, efecto_tipo: str) -> EstrategiaUbicacion:
        """Retorna la estrategia registrada para efecto_tipo o la estrategia libre por defecto."""
        return self._efectos.get(efecto_tipo, self._efecto_por_defecto)

    def obtener_energia(self, energia_tipo: str) -> EstrategiaEnergiaUbicacion:
        """Retorna la estrategia registrada para energia_tipo o lanza ValueError."""
        estrategia = self._energias.get(energia_tipo)
        if estrategia is None:
            raise ValueError(f"Tipo de energía de ubicación no soportado: {energia_tipo!r}")
        return estrategia


REGISTRO_ESTRATEGIAS_POR_DEFECTO = RegistroEstrategiasUbicacion(
    efectos={
        "BONIFICACION_POR_TIPO": EstrategiaEfectoLibre(),
        "MODIFICADOR_COSTO": EstrategiaEfectoLibre(),
        "NINGUNO": EstrategiaEfectoLibre(),
        "RESTRICCION_TURNO": EstrategiaRestriccionTurno(),
    },
    energias={
        "FIJA": EstrategiaEnergiaFija(),
        "POR_CARTAS": EstrategiaEnergiaPorCartas(),
    },
)


def es_ubicacion_jugable(
    ubicacion: UbicacionSnapshot,
    *,
    registro: RegistroEstrategiasUbicacion | None = None,
    turnos_partida: frozenset[int] = TURNOS_PARTIDA,
) -> bool:
    """Evalúa si una ubicación permite jugar cartas en al menos un turno de la partida."""
    if ubicacion.card_limit <= 0:
        return False
    reg = registro if registro is not None else REGISTRO_ESTRATEGIAS_POR_DEFECTO
    estrategia = reg.obtener_efecto(ubicacion.efecto_tipo)
    return estrategia.permite_jugar_en_algun_turno(ubicacion, turnos_partida)


def calcular_energia_extra_ubicacion(
    ubicacion: UbicacionSnapshot,
    cartas_propias_en_ubicacion: int,
    *,
    registro: RegistroEstrategiasUbicacion | None = None,
) -> int:
    """Calcula el bono de energía aportado por una ubicación para un jugador."""
    if isinstance(cartas_propias_en_ubicacion, bool) or not isinstance(
        cartas_propias_en_ubicacion, int
    ):
        raise ValueError("cartas_propias_en_ubicacion debe ser un entero")
    if cartas_propias_en_ubicacion < 0:
        raise ValueError("cartas_propias_en_ubicacion no puede ser negativo")
    reg = registro if registro is not None else REGISTRO_ESTRATEGIAS_POR_DEFECTO
    estrategia = reg.obtener_energia(ubicacion.energia_tipo)
    return estrategia.calcular_energia_extra(ubicacion, cartas_propias_en_ubicacion)


__all__ = [
    "EstrategiaEfectoLibre",
    "EstrategiaEnergiaFija",
    "EstrategiaEnergiaPorCartas",
    "EstrategiaEnergiaUbicacion",
    "EstrategiaRestriccionTurno",
    "EstrategiaUbicacion",
    "REGISTRO_ESTRATEGIAS_POR_DEFECTO",
    "RegistroEstrategiasUbicacion",
    "calcular_energia_extra_ubicacion",
    "es_ubicacion_jugable",
]
