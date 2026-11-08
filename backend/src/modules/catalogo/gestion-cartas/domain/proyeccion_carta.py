"""Contrato del evento de creación y de la representación derivada de carta."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class EventoIncompatible(Exception):
    """El evento requiere revisión operativa y conserva su cuerpo en Outbox."""


class ProyeccionTemporal(Exception):
    """No se pudo verificar todavía el efecto esperado en MongoDB."""


class OutboxTemporal(Exception):
    """Una operación SQL no pudo confirmarse de forma segura."""


@dataclass(frozen=True, slots=True)
class EventoReclamado:
    """Evento durable y token nuevo que autoriza exactamente una reclamación."""

    id: str
    tipo: str
    agregado: str
    version: int
    esquema: int
    correlacion: str | None
    creado: datetime
    sobre: object
    intento: int
    token: str

    def contenido(self) -> dict[str, str | int]:
        """Valida el sobre v1 antes de acceder a los datos de la carta."""
        if self.tipo != "CardCreated" or self.esquema != 1 or self.version < 1:
            raise EventoIncompatible("evento_version_incompatible")
        if not all(_uuid(valor) for valor in (self.id, self.agregado, self.correlacion)):
            raise EventoIncompatible("identificador_invalido")
        if self.creado.utcoffset() is None or not isinstance(self.sobre, dict):
            raise EventoIncompatible("sobre_invalido")
        esperado = {
            "event_id": self.id,
            "aggregate_id": self.agregado,
            "aggregate_version": self.version,
            "schema_version": self.esquema,
            "correlation_id": self.correlacion,
        }
        if any(
            type(self.sobre.get(k)) is not type(v) or self.sobre.get(k) != v
            for k, v in esperado.items()
        ):
            raise EventoIncompatible("sobre_invalido")
        datos = self.sobre.get("payload")
        if not isinstance(datos, dict) or not all(
            isinstance(k, str) and type(v) in (str, int) for k, v in datos.items()
        ):
            raise EventoIncompatible("payload_invalido")
        return datos


def _uuid(valor: str | None) -> bool:
    if valor is None:
        return False
    try:
        return str(UUID(valor)) == valor
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class ProyeccionCarta:
    """Campos SQL confirmados y versión del agregado que se puede publicar."""

    id: str
    version: int
    campos: dict[str, str | int]

    def documento(self) -> dict[str, str | int]:
        """Construye el documento sin serializar el sobre ni archivos de imagen."""
        return self.campos | {"_id": self.id, "aggregate_version": self.version}
