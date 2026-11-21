"""Representación derivada de carta para sincronización directa y reconciliación."""

from dataclasses import dataclass
from typing import Any


class EventoIncompatible(Exception):
    """Conflicto de integridad al proyectar una carta hacia MongoDB."""


class ProyeccionTemporal(Exception):
    """No se pudo confirmar temporalmente la operación en MongoDB."""


class FuenteSqlTemporal(Exception):
    """No se pudo leer temporalmente el snapshot autoritativo en PostgreSQL."""


@dataclass(frozen=True, slots=True)
class ProyeccionCarta:
    """Campos SQL confirmados y versión del agregado que se proyectan en MongoDB."""

    id: str
    version: int
    campos: dict[str, Any]

    def documento(self) -> dict[str, Any]:
        """Construye el documento completo de lectura para cards_projection."""
        return self.campos | {"_id": self.id, "aggregate_version": self.version}
