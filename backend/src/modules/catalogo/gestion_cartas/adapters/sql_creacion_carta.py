"""Adaptador transaccional de Crear Carta sobre los modelos y engine oficiales."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from hashlib import sha256

from sqlalchemy import ColumnElement, or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from src.database.postgresql.destino_original import IDENTIDAD_SQL, destino_original_activo
from src.database.postgresql.revisiones import REVISION_TIPO_CUENTA, REVISIONES_CARTAS
from src.shared.destinos_originales import PG_ORIGINAL
from src.shared.idempotencia.models import IdempotencyRecordORM
from src.shared.outbox import OutboxEventORM

from ..domain.carta_model import Carta
from ..domain.imagen_model import (
    FormatoImagen,
    ImagenAlmacenada,
    MetadatosImagen,
    ReferenciasImagen,
)
from ..ports.cartas_ports import ErrorPersistencia, TipoErrorPersistencia
from ..ports.creacion_ports import (
    COMPENSACION_PENDIENTE,
    ClaveCreacion,
    ClaveOcupada,
    CommitIncierto,
    OperacionCreacionPort,
    RegistroCreacion,
    TransaccionCreacionPort,
)
from .cartas_orm import CartaORM, ImagenCartaORM
from .sql_carta_repository import SqlCartaRepository

ESTADOS_RESERVA = ("PENDING", "RETRY_PENDING")


def _fallo_sql() -> ErrorPersistencia:
    return ErrorPersistencia(TipoErrorPersistencia.OPERACION)


def _usa_reserva(operacion_id: str) -> ColumnElement[bool]:
    """Localiza una carta que ya ocupa la identidad o la imagen reservada."""
    return or_(CartaORM.id == operacion_id, CartaORM.image_id == operacion_id)


def _imagen_registrada(fila: ImagenCartaORM) -> ImagenAlmacenada | None:
    """Reconstruye las referencias y metadatos de una reserva completa."""
    clave, formato = fila.thumbnail_storage_key, fila.thumbnail_format
    ancho, alto, tamano = fila.thumbnail_width, fila.thumbnail_height, fila.thumbnail_byte_size
    if clave is None or formato is None or ancho is None or alto is None or tamano is None:
        return None
    return ImagenAlmacenada(
        ReferenciasImagen(fila.original_storage_key, clave),
        MetadatosImagen(
            FormatoImagen(fila.image_format),
            fila.width,
            fila.height,
            fila.byte_size,
            fila.original_sha256,
        ),
        MetadatosImagen(FormatoImagen(formato), ancho, alto, tamano),
    )


class SqlTransaccionCreacion(TransaccionCreacionPort):
    """Vincula los repositorios y modelos existentes a una sola sesión."""

    def __init__(self, session: AsyncSession) -> None:
        """Recibe una sesión con BEGIN explícito administrado por la operación."""
        self._session = session
        self._cartas = SqlCartaRepository(session)

    @property
    def cartas(self) -> SqlCartaRepository:
        """Devuelve el repositorio existente enlazado a la transacción."""
        return self._cartas

    async def obtener(self, clave: ClaveCreacion) -> RegistroCreacion | None:
        """Lee la clave con bloqueo SQL durante esta transacción corta."""
        registro = await self._session.scalar(
            select(IdempotencyRecordORM)
            .where(
                IdempotencyRecordORM.actor_id == clave.actor,
                IdempotencyRecordORM.operation == clave.operacion,
                IdempotencyRecordORM.idempotency_key == clave.clave,
            )
            .with_for_update()
        )
        if registro is None:
            return None
        fila = None
        codigo = None
        if registro.resource_id == registro.id:
            if registro.response_status is None:
                fila = await self._session.scalar(
                    select(ImagenCartaORM).where(
                        ImagenCartaORM.id == registro.id,
                        ~select(CartaORM.id).where(_usa_reserva(registro.id)).exists(),
                    )
                )
            elif registro.response_status == 201:
                codigo = await self._session.scalar(
                    select(CartaORM.code)
                    .join(ImagenCartaORM, ImagenCartaORM.id == CartaORM.image_id)
                    .where(
                        CartaORM.id == registro.id,
                        ImagenCartaORM.id == registro.id,
                        ImagenCartaORM.state == "READY",
                    )
                )
        return RegistroCreacion(
            registro.id,
            registro.resource_id,
            registro.request_hash,
            registro.response_status,
            registro.response_body,
            _imagen_registrada(fila) if fila is not None else None,
            fila.state if fila is not None else None,
            fila is not None and fila.sanitized_error == COMPENSACION_PENDIENTE,
            codigo,
        )

    async def reservar(
        self,
        clave: ClaveCreacion,
        operacion_id: str,
        huella: str,
        imagen: ImagenAlmacenada,
        ahora: datetime,
    ) -> None:
        """Inserta una imagen pendiente y su reserva bajo la unicidad de alcance."""
        original, miniatura = imagen.original, imagen.miniatura
        self._session.add_all(
            [
                IdempotencyRecordORM(
                    id=operacion_id,
                    resource_id=operacion_id,
                    actor_id=clave.actor,
                    operation=clave.operacion,
                    endpoint=clave.operacion,
                    idempotency_key=clave.clave,
                    request_hash=huella,
                    created_at=ahora,
                ),
                ImagenCartaORM(
                    id=operacion_id,
                    original_storage_key=imagen.referencias.original,
                    original_sha256=original.sha256,
                    image_format=original.formato,
                    width=original.ancho,
                    height=original.alto,
                    byte_size=original.tamano,
                    thumbnail_storage_key=imagen.referencias.miniatura,
                    thumbnail_format=miniatura.formato,
                    thumbnail_width=miniatura.ancho,
                    thumbnail_height=miniatura.alto,
                    thumbnail_byte_size=miniatura.tamano,
                    state="PENDING",
                    attempts=1,
                    created_at=ahora,
                    updated_at=ahora,
                ),
            ]
        )
        await self._session.flush()

    async def _actualizar_pendiente(
        self,
        operacion_id: str,
        ahora: datetime,
        *,
        terminar_compensacion: bool = False,
        **valores: object,
    ) -> None:
        """Actualiza una reserva no publicada y exige que exista exactamente una."""
        compensacion = ImagenCartaORM.sanitized_error.is_not_distinct_from(COMPENSACION_PENDIENTE)
        actualizado = await self._session.scalar(
            update(ImagenCartaORM)
            .where(
                ImagenCartaORM.id == operacion_id,
                ImagenCartaORM.state.in_(ESTADOS_RESERVA),
                compensacion if terminar_compensacion else ~compensacion,
            )
            .values(updated_at=ahora, **valores)
            .returning(ImagenCartaORM.id)
        )
        if actualizado is None:
            raise _fallo_sql()

    async def registrar_intento(self, operacion_id: str, ahora: datetime) -> None:
        """Incrementa intentos dentro de la transacción previa a GridFS."""
        await self._actualizar_pendiente(
            operacion_id,
            ahora,
            attempts=ImagenCartaORM.attempts + 1,
        )

    async def registrar_fallo(self, operacion_id: str, error: str, ahora: datetime) -> None:
        """Conserva referencias para conciliación y anota una categoría segura."""
        await self._actualizar_pendiente(
            operacion_id,
            ahora,
            state="RETRY_PENDING",
            sanitized_error=error,
        )

    async def puede_compensar(self, operacion_id: str, imagen: ImagenAlmacenada) -> bool:
        """Comprueba propiedad de referencias y ausencia de una carta confirmada."""
        carta = await self._session.scalar(
            select(CartaORM.id).where(_usa_reserva(operacion_id)).limit(1)
        )
        if carta is not None:
            return False
        refs = (imagen.referencias.original, imagen.referencias.miniatura)
        ajena = await self._session.scalar(
            select(ImagenCartaORM.id)
            .where(
                ImagenCartaORM.id != operacion_id,
                or_(
                    ImagenCartaORM.original_storage_key.in_(refs),
                    ImagenCartaORM.thumbnail_storage_key.in_(refs),
                ),
            )
            .limit(1)
        )
        return ajena is None

    async def terminar_compensacion(self, operacion_id: str, ahora: datetime) -> None:
        """Retira el bloqueo durable solo si la fila sigue pendiente de limpieza."""
        await self._actualizar_pendiente(
            operacion_id, ahora, terminar_compensacion=True, sanitized_error=None
        )

    async def marcar_lista(self, operacion_id: str, ahora: datetime) -> None:
        """Actualiza READY tras la verificación hecha fuera de SQL."""
        await self._actualizar_pendiente(
            operacion_id,
            ahora,
            state="READY",
            sanitized_error=None,
        )

    async def agregar_evento(self, carta: Carta, payload: dict[str, str | int]) -> None:
        """Guarda CardCreated con el sobre versionado y correlación de la reserva."""
        self._session.add(
            OutboxEventORM(
                id=carta.id,
                event_type="CardCreated",
                aggregate_type="card",
                aggregate_id=carta.id,
                aggregate_version=carta.version,
                schema_version=1,
                correlation_id=carta.id,
                status="PENDING",
                attempts=0,
                created_at=carta.created_at,
                payload={
                    "event_id": carta.id,
                    "aggregate_id": carta.id,
                    "aggregate_version": carta.version,
                    "schema_version": 1,
                    "correlation_id": carta.id,
                    "payload": payload,
                },
            )
        )
        await self._session.flush()

    async def confirmar(self, operacion_id: str, respuesta: dict[str, str | int]) -> None:
        """Completa el par de respuesta existente y exige una reserva pendiente."""
        confirmado = await self._session.scalar(
            update(IdempotencyRecordORM)
            .where(
                IdempotencyRecordORM.id == operacion_id,
                IdempotencyRecordORM.response_status.is_(None),
            )
            .values(response_status=201, response_body=respuesta)
            .returning(IdempotencyRecordORM.id)
        )
        if confirmado is None:
            raise _fallo_sql()


class SqlOperacionCreacion(OperacionCreacionPort):
    """Transacciones cortas sobre la conexión que posee el lock de sesión."""

    def __init__(
        self,
        conn: AsyncConnection,
        factory: async_sessionmaker[AsyncSession],
        pid: int,
    ) -> None:
        """Ancla la operación a la sesión PostgreSQL que adquirió la exclusión."""
        self._conn, self._factory, self._pid = conn, factory, pid

    @asynccontextmanager
    async def transaccion(self) -> AsyncIterator[TransaccionCreacionPort]:
        """Clasifica fallos de commit sin asumir que implican rollback."""
        entrando_commit = False
        try:
            if self._conn.invalidated:
                raise _fallo_sql()
            async with self._factory(bind=self._conn) as session, session.begin():
                if await session.scalar(text("SELECT pg_backend_pid()")) != self._pid:
                    raise _fallo_sql()
                yield SqlTransaccionCreacion(session)
                entrando_commit = True
        except SQLAlchemyError:
            if entrando_commit:
                raise CommitIncierto(TipoErrorPersistencia.OPERACION) from None
            raise _fallo_sql() from None


class SqlCoordinacionCreacion:
    """Exclusión por alcance idempotente sin mantener BEGIN durante GridFS."""

    def __init__(self, engine: AsyncEngine, factory: async_sessionmaker[AsyncSession]) -> None:
        """Reutiliza el engine y la configuración de sesiones oficiales."""
        self._engine, self._factory = engine, factory

    @asynccontextmanager
    async def exclusiva(self, clave: ClaveCreacion) -> AsyncIterator[OperacionCreacionPort]:
        """Mantiene el lock de sesión y lo libera antes de devolver la conexión."""
        scope = json.dumps((clave.actor, clave.operacion, clave.clave), separators=(",", ":"))
        llave = int.from_bytes(sha256(scope.encode()).digest()[:8], "big", signed=True)
        parametros = {"llave": llave}
        try:
            async with self._engine.connect() as conn:
                adquirido: bool | None = False
                try:
                    async with conn.begin():
                        identidad = tuple((await conn.execute(IDENTIDAD_SQL)).one())
                        base = identidad[0]
                        original = base == PG_ORIGINAL[2]
                        permitido = (
                            destino_original_activo(identidad, "api") if original
                            else base.startswith("pokearena_alembic_")
                        )
                        if not permitido:
                            raise _fallo_sql()
                        revisiones = {REVISION_TIPO_CUENTA} if original else REVISIONES_CARTAS
                        if (
                            await conn.scalar(text("SELECT version_num FROM alembic_version"))
                            not in revisiones
                        ):
                            raise _fallo_sql()
                        pid = await conn.scalar(text("SELECT pg_backend_pid()"))
                        if not isinstance(pid, int):
                            raise _fallo_sql()
                        adquirido = None  # La cancelación puede ocultar la respuesta del lock.
                        adquirido = await conn.scalar(
                            text("SELECT pg_try_advisory_lock(CAST(:llave AS bigint))"), parametros
                        )
                    if adquirido is not True:
                        raise ClaveOcupada()
                    yield SqlOperacionCreacion(conn, self._factory, pid)
                finally:
                    if adquirido is not False:
                        await self._liberar(conn, parametros, adquirido is True)
        except SQLAlchemyError:
            raise _fallo_sql() from None

    @staticmethod
    async def _liberar(
        conn: AsyncConnection,
        parametros: dict[str, int],
        confirmado: bool,
    ) -> None:
        """Descarta conexiones con un lock de resultado incierto antes de reciclarlas."""
        if not confirmado or conn.invalidated:
            await conn.invalidate()
            return
        try:
            async with conn.begin():
                liberado = await conn.scalar(
                    text("SELECT pg_advisory_unlock(CAST(:llave AS bigint))"), parametros
                )
            if liberado is not True:
                await conn.invalidate()
        except SQLAlchemyError:
            await conn.invalidate()
        except BaseException:
            await conn.invalidate()
            raise
