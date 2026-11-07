"""Composición SQL sin registrar API, conectar motores ni activar workers.

Punto único de carga explícita aprobado para gestion-cartas: importlib acepta
guiones, la sintaxis from/import no. Las dependencias internas son relativas.
"""

from importlib import import_module
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.postgresql.base import Base
from src.shared.idempotencia.models import IdempotencyRecordORM
from src.shared.outbox import OutboxEventORM

_PAQUETE = f"{__package__}.gestion-cartas"
dominio_cartas = import_module(f"{_PAQUETE}.domain.carta_model")
puertos_cartas = import_module(f"{_PAQUETE}.ports.cartas_ports")
_orm = import_module(f"{_PAQUETE}.adapters.cartas_orm")
_repositorio = import_module(f"{_PAQUETE}.adapters.sql_carta_repository")


def modelos_persistencia() -> tuple[type[Base], ...]:
    """Expone seis mapeos únicos sin DDL; metadata parcial no apta para autogenerate."""
    return (
        _orm.CartaORM, _orm.HabilidadORM, _orm.ImagenCartaORM, _orm.ContadorCartaORM,
        IdempotencyRecordORM, OutboxEventORM,
    )


def crear_repositorio_cartas(session: AsyncSession) -> Any:
    """Inyecta sesión, sin transacciones ni HTTP; frontera dinámica explícita.

    Any está limitado a esta composición: importlib devuelve módulos sin tipos
    estáticos de sus miembros. El adaptador implementa el puerto tipado original,
    verificado por Mypy con su nombre de módulo y por pruebas de composición.
    """
    return _repositorio.SqlCartaRepository(session)

