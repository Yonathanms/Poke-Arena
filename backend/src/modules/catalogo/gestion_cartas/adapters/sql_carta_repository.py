"""Adaptador SQL asíncrono: sesión inyectada y transacción propiedad del llamador."""

from copy import deepcopy
from dataclasses import asdict

from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import SessionTransactionOrigin

from ..domain.carta_model import Carta, Habilidad
from ..ports.cartas_ports import CartasRepositoryPort, ErrorPersistencia, TipoErrorPersistencia
from .cartas_orm import CartaORM, ContadorCartaORM, HabilidadORM, ImagenCartaORM


def _traducir_error(error: DBAPIError) -> ErrorPersistencia:
    """Extrae únicamente SQLSTATE/constraint del driver; descarta SQL y valores."""
    original = error.orig
    causa = getattr(original, "__cause__", None)
    valor_codigo = getattr(original, "sqlstate", None) or getattr(causa, "sqlstate", None)
    codigo = valor_codigo if isinstance(valor_codigo, str) else ""
    tipo = {
        "23505": TipoErrorPersistencia.DUPLICADO,
        "23503": TipoErrorPersistencia.REFERENCIA,
        "23514": TipoErrorPersistencia.RESTRICCION,
        "23502": TipoErrorPersistencia.RESTRICCION,
        "P0001": TipoErrorPersistencia.RESTRICCION,
    }.get(codigo, TipoErrorPersistencia.OPERACION)
    restriccion = getattr(causa, "constraint_name", None)
    return ErrorPersistencia(tipo, restriccion if isinstance(restriccion, str) else None)


def _a_carta(fila: CartaORM) -> Carta:
    """Separa estado escalar del ORM para no exportar entidades con sesión."""
    return Carta(
        id=fila.id,
        code=fila.code,
        name=fila.name,
        cost=fila.cost,
        power=fila.power,
        card_type=fila.card_type,
        rarity=fila.rarity,
        ability_id=fila.ability_id,
        image_id=fila.image_id,
        version=fila.version,
        created_at=fila.created_at,
    )


class SqlCartaRepository(CartasRepositoryPort):
    """Acceso técnico; no asigna códigos ni coordina Crear carta.

    El consumidor abre una transacción y la revierte ante fallo. No compartir
    una AsyncSession entre tareas concurrentes.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Recibe sesión oficial o aislada; no crea conexiones."""
        self._session = session

    def _exigir_transaccion(self) -> None:
        """Exige BEGIN raíz explícito y activo; AUTOBEGIN no acredita al llamador.

        sync_session y SessionTransaction.origin son API pública de SQLAlchemy 2.
        No se altera la fábrica ni se toma control de commit/rollback.
        """
        transaccion = self._session.sync_session.get_transaction()
        if (
            transaccion is None
            or not transaccion.is_active
            or transaccion.origin is not SessionTransactionOrigin.BEGIN
        ):
            raise RuntimeError("El llamador debe abrir una transacción explícita")

    async def buscar_por_id(self, carta_id: str) -> Carta | None:
        """Consulta PK y devuelve estado puro, sin confirmar la transacción."""
        self._exigir_transaccion()
        try:
            fila = await self._session.scalar(select(CartaORM).where(CartaORM.id == carta_id))
        except DBAPIError as error:
            raise _traducir_error(error) from None
        return _a_carta(fila) if fila else None

    async def buscar_por_codigo(self, codigo: str) -> Carta | None:
        """Consulta código; None indica ausencia sin crear recursos."""
        self._exigir_transaccion()
        try:
            fila = await self._session.scalar(select(CartaORM).where(CartaORM.code == codigo))
        except DBAPIError as error:
            raise _traducir_error(error) from None
        return _a_carta(fila) if fila else None

    async def buscar_referencia_miniatura(self, carta_id: str) -> str | None:
        """Lee únicamente la referencia WebP lista de la carta solicitada."""
        self._exigir_transaccion()
        try:
            return await self._session.scalar(
                select(ImagenCartaORM.thumbnail_storage_key)
                .join(CartaORM, CartaORM.image_id == ImagenCartaORM.id)
                .where(
                    CartaORM.id == carta_id,
                    ImagenCartaORM.state == "READY",
                    ImagenCartaORM.thumbnail_format == "WEBP",
                    ImagenCartaORM.thumbnail_storage_key != ImagenCartaORM.original_storage_key,
                )
            )
        except DBAPIError as error:
            raise _traducir_error(error) from None

    async def buscar_referencia_original(self, carta_id: str) -> str | None:
        """Lee únicamente la referencia original de la carta solicitada."""
        self._exigir_transaccion()
        try:
            return await self._session.scalar(
                select(ImagenCartaORM.original_storage_key)
                .join(CartaORM, CartaORM.image_id == ImagenCartaORM.id)
                .where(
                    CartaORM.id == carta_id,
                    ImagenCartaORM.state == "READY",
                )
            )
        except DBAPIError as error:
            raise _traducir_error(error) from None

    async def buscar_habilidad_por_codigo(self, codigo: str) -> Habilidad | None:
        """Lee habilidad y copia JSON para no filtrar estado mutable del ORM."""
        self._exigir_transaccion()
        try:
            fila = await self._session.scalar(
                select(HabilidadORM).where(HabilidadORM.code == codigo)
            )
        except DBAPIError as error:
            raise _traducir_error(error) from None
        if fila is None:
            return None
        return Habilidad(
            id=fila.id,
            code=fila.code,
            name=fila.name,
            ability_type=fila.ability_type,
            description=fila.description,
            params=deepcopy(fila.params),
            has_effect=fila.has_effect,
            evolution_target_card_id=fila.evolution_target_card_id,
        )

    async def agregar(self, carta: Carta) -> None:
        """Inserta y hace flush; ErrorPersistencia exige rollback de la unidad completa."""
        self._exigir_transaccion()
        self._session.add(CartaORM(**asdict(carta)))
        try:
            await self._session.flush()
        except DBAPIError as error:
            raise _traducir_error(error) from None

    async def bloquear_contador(self, tipo: str) -> int | None:
        """Bloquea fila existente sin implementar política de asignación."""
        self._exigir_transaccion()
        try:
            return await self._session.scalar(
                select(ContadorCartaORM.last_value)
                .where(ContadorCartaORM.card_type == tipo)
                .with_for_update()
            )
        except DBAPIError as error:
            raise _traducir_error(error) from None

    async def actualizar_contador(self, tipo: str, valor: int) -> None:
        """Actualiza el contador bloqueado por el llamador en esta transacción."""
        self._exigir_transaccion()
        try:
            actualizado = await self._session.scalar(
                update(ContadorCartaORM)
                .where(ContadorCartaORM.card_type == tipo)
                .values(last_value=valor)
                .returning(ContadorCartaORM.card_type)
            )
        except DBAPIError as error:
            raise _traducir_error(error) from None
        if actualizado is None:
            raise ErrorPersistencia(TipoErrorPersistencia.OPERACION)

    async def ruta_evolucion(self, destino: str) -> tuple[str, ...]:
        """Sigue las FK y termina al repetir un nodo mediante CYCLE de PostgreSQL."""
        self._exigir_transaccion()
        try:
            ruta = await self._session.scalars(
                text(
                    "WITH RECURSIVE ruta(id, destino) AS ("
                    " SELECT c.id, a.evolution_target_card_id FROM catalog_cards c"
                    " JOIN catalog_abilities a ON a.id=c.ability_id WHERE c.id=:destino"
                    " UNION ALL SELECT c.id, a.evolution_target_card_id FROM ruta"
                    " JOIN catalog_cards c ON c.id=ruta.destino"
                    " JOIN catalog_abilities a ON a.id=c.ability_id"
                    ") CYCLE id SET ciclo USING camino SELECT id FROM ruta"
                ),
                {"destino": destino},
            )
        except DBAPIError as error:
            raise _traducir_error(error) from None
        return tuple(ruta)

    async def listar_habilidades(self) -> list[tuple[str, str]]:
        """Lee códigos y nombres de habilidades existentes en orden de selección."""
        self._exigir_transaccion()
        try:
            filas = await self._session.execute(
                select(HabilidadORM.code, HabilidadORM.name).order_by(HabilidadORM.code)
            )
        except DBAPIError as error:
            raise _traducir_error(error) from None
        return [(codigo, nombre) for codigo, nombre in filas.tuples()]
