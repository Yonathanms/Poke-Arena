"""Reclama y resuelve CardCreated con fencing sobre el Outbox existente."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.outbox import OutboxEventORM

from ..domain.proyeccion_carta import (
    EventoIncompatible,
    EventoReclamado,
    OutboxTemporal,
    ProyeccionCarta,
)
from .cartas_orm import CartaORM, HabilidadORM, ImagenCartaORM

Evento = OutboxEventORM
_ALCANCE = (Evento.event_type == "CardCreated", Evento.aggregate_type == "card")
_ELEGIBLE = or_(
    Evento.status.in_(("PENDING", "RETRY_PENDING"))
    & or_(Evento.next_attempt_at.is_(None), Evento.next_attempt_at <= func.clock_timestamp()),
    (Evento.status == "PROCESSING")
    & or_(Evento.lease_expires_at.is_(None), Evento.lease_expires_at <= func.clock_timestamp()),
)


class SqlOutboxCartas:
    """Usa el primario y transacciones cortas de la fábrica PostgreSQL oficial."""

    def __init__(
        self, factory: async_sessionmaker[AsyncSession], lease_segundos: int, max_intentos: int
    ) -> None:
        """Recibe la fábrica oficial y los límites de reclamación."""
        self._factory, self._lease, self._max_intentos = factory, lease_segundos, max_intentos

    @asynccontextmanager
    async def _transaccion(self) -> AsyncIterator[AsyncSession]:
        """Traduce fallos SQL, incluso de commit, sin exponer datos del driver."""
        try:
            async with self._factory() as sesion, sesion.begin():
                yield sesion
        except SQLAlchemyError:
            raise OutboxTemporal() from None

    async def reclamar(self, limite: int) -> list[EventoReclamado]:
        """Reclama filas elegibles y agota leases vencidos sin abrir I/O MongoDB."""
        async with self._transaccion() as sesion:
            await self._verificar_destino(sesion)
            candidatos = (
                select(Evento.id)
                .where(*_ALCANCE, _ELEGIBLE, Evento.attempts >= self._max_intentos)
                .order_by(Evento.created_at, Evento.id)
                .limit(limite)
                .with_for_update(skip_locked=True)
            )
            await sesion.execute(
                update(Evento)
                .where(Evento.id.in_(candidatos))
                .values(
                    status="FAILED",
                    sanitized_error="intentos_agotados",
                    next_attempt_at=None,
                    lease_token=None,
                    lease_expires_at=None,
                )
            )
            filas = (
                await sesion.scalars(
                    select(Evento)
                    .where(*_ALCANCE, _ELEGIBLE, Evento.attempts < self._max_intentos)
                    .order_by(Evento.created_at, Evento.id)
                    .limit(limite)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            reclamados = []
            if filas:
                ahora = (await sesion.execute(select(func.clock_timestamp()))).scalar_one()
                for fila in filas:
                    token = str(uuid4())
                    fila.status = "PROCESSING"
                    fila.processed_at = None
                    fila.attempts += 1
                    fila.lease_token = token
                    fila.lease_expires_at = ahora + timedelta(seconds=self._lease)
                    fila.next_attempt_at = None
                    reclamados.append(
                        EventoReclamado(
                            fila.id,
                            fila.event_type,
                            fila.aggregate_id,
                            fila.aggregate_version,
                            fila.schema_version,
                            fila.correlation_id,
                            fila.created_at,
                            fila.payload,
                            fila.attempts,
                            token,
                        )
                    )
            return reclamados

    @staticmethod
    async def _verificar_destino(sesion: AsyncSession) -> None:
        """Impide reclamar filas de una base original o con revisión distinta."""
        base, admin = (
            await sesion.execute(
                text(
                    "SELECT current_database(), rolsuper FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one()
        if not base.startswith("pokearena_alembic_") or admin:
            raise ValueError("destino_postgresql_fuera_de_1f")
        if await sesion.scalar(text("SELECT version_num FROM alembic_version")) != (
            "1b2b_card_image_integrity"
        ):
            raise ValueError("revision_postgresql_fuera_de_1f")

    async def proyeccion(
        self, evento: EventoReclamado, contenido: dict[str, str | int]
    ) -> ProyeccionCarta:
        """Lee la carta, habilidad y estado READY con un solo snapshot SQL."""
        async with self._transaccion() as sesion:
            fila = (
                await sesion.execute(
                    select(CartaORM, HabilidadORM.code, ImagenCartaORM.state)
                    .join(HabilidadORM, HabilidadORM.id == CartaORM.ability_id)
                    .join(ImagenCartaORM, ImagenCartaORM.id == CartaORM.image_id)
                    .where(CartaORM.id == evento.agregado)
                )
            ).one_or_none()
        if fila is None:
            raise EventoIncompatible("agregado_no_verificable")
        carta, habilidad, estado = fila
        if estado != "READY" or carta.image_id is None or carta.version != evento.version:
            raise EventoIncompatible("snapshot_sql_incompatible")
        campos: dict[str, str | int] = {
            "id": carta.id,
            "code": carta.code,
            "name": carta.name,
            "card_type": carta.card_type,
            "rarity": carta.rarity,
            "cost": carta.cost,
            "power": carta.power,
            "ability_id": carta.ability_id,
            "ability_code": habilidad,
            "image_id": carta.image_id,
            "image_status": estado,
        }
        if campos != contenido:
            raise EventoIncompatible("payload_discrepa_de_sql")
        return ProyeccionCarta(carta.id, carta.version, campos)

    async def resolver(
        self, evento: EventoReclamado, error: str | None, demora: int | None = None
    ) -> bool:
        """Actualiza únicamente el token vigente y evita esperar por otro dueño."""
        async with self._transaccion() as sesion:
            titular = (
                Evento.id == evento.id,
                Evento.status == "PROCESSING",
                Evento.lease_token == evento.token,
                *_ALCANCE,
            )
            fila = await sesion.scalar(
                select(Evento.id).where(*titular).with_for_update(skip_locked=True)
            )
            if fila is None:
                return False
            ahora = func.clock_timestamp()
            reintentar = demora is not None and evento.intento < self._max_intentos
            confirmado = await sesion.scalar(
                update(Evento)
                .where(*titular, Evento.lease_expires_at > ahora)
                .values(
                    status="PROCESSED"
                    if error is None
                    else "RETRY_PENDING"
                    if reintentar
                    else "FAILED",
                    processed_at=ahora if error is None else None,
                    next_attempt_at=ahora + timedelta(seconds=demora)
                    if reintentar and demora is not None
                    else None,
                    sanitized_error=error,
                    lease_token=None,
                    lease_expires_at=None,
                )
                .returning(Evento.id)
            )
            return confirmado is not None
