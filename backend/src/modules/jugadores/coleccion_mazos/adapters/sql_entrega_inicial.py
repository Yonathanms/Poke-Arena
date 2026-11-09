"""Persistencia PostgreSQL para la provisión de la colección inicial."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.entrega_inicial_model import (
    INITIAL_CARD_COUNT,
    INITIAL_COLLECTION,
    INITIAL_CUBES,
    CartaPaquete,
    PerfilProvision,
    ProvisionNoDisponible,
)
from ..ports.entrega_inicial_ports import TransaccionEntregaInicial

type AutorizarJugador = Callable[[str], Awaitable[str | None]]


class SqlTransaccionEntregaInicial:
    """Usa la sesión compartida de la unidad de trabajo sin commits propios."""

    def __init__(self, sesion: AsyncSession, autorizar: AutorizarJugador) -> None:
        self._sesion = sesion
        self._autorizar = autorizar

    async def jugador_elegible(self, token_sesion: str) -> str | None:
        """Delega en Identidad dentro de la transacción en curso."""
        return await self._autorizar(token_sesion)

    async def bloquear_perfil(self, usuario_id: str) -> PerfilProvision | None:
        """Lee el perfil vigente tras adquirir su bloqueo exclusivo."""
        return await self._perfil(usuario_id, "FOR UPDATE")

    async def leer_perfil(self, usuario_id: str) -> PerfilProvision | None:
        """Estabiliza el perfil frente a provisión y apertura durante la lectura."""
        return await self._perfil(usuario_id, "FOR SHARE")

    async def _perfil(self, usuario_id: str, bloqueo: str) -> PerfilProvision | None:
        fila = (await self._sesion.execute(
            text(f"""
                SELECT cubes, has_received_initial_collection, initial_pack_opened_at
                FROM player_profiles WHERE user_id = :usuario {bloqueo}
            """),
            {"usuario": usuario_id},
        )).one_or_none()
        return PerfilProvision(*fila) if fila is not None else None

    async def cartas_del_paquete(self, usuario_id: str) -> tuple[CartaPaquete, ...]:
        """Lee el inventario y su catálogo en orden estable."""
        filas = await self._sesion.execute(
            text("""
                SELECT c.id, c.code, c.name, p.quantity
                FROM player_cards p JOIN catalog_cards c ON c.id = p.card_id
                WHERE p.user_id = :usuario
                ORDER BY c.id
                LIMIT :maximo
            """),
            {"usuario": usuario_id, "maximo": INITIAL_CARD_COUNT + 1},
        )
        return tuple(CartaPaquete(*fila) for fila in filas)

    async def movimiento_inicial_integro(self, usuario_id: str) -> bool:
        """Verifica que existe exactamente un movimiento y tiene los datos iniciales."""
        return bool(await self._sesion.scalar(
            text("""
                SELECT count(*) = 1 AND count(*) FILTER (
                    WHERE reason = :motivo AND amount = :cubos AND balance_after = :cubos
                ) = 1
                FROM cube_transactions WHERE user_id = :usuario
            """),
            {"usuario": usuario_id, "motivo": INITIAL_COLLECTION, "cubos": INITIAL_CUBES},
        ))

    async def registrar_apertura(self, usuario_id: str) -> datetime:
        """Persiste el timestamp del servidor únicamente para un perfil aún cerrado."""
        fila = await self._sesion.execute(
            text("""
                UPDATE player_profiles SET initial_pack_opened_at = statement_timestamp()
                WHERE user_id = :usuario AND initial_pack_opened_at IS NULL
                RETURNING initial_pack_opened_at
            """),
            {"usuario": usuario_id},
        )
        instante: datetime = fila.scalar_one()
        return instante

    async def tiene_inventario_o_historial(self, usuario_id: str) -> bool:
        """Comprueba las precondiciones de la primera entrega en el estado vigente."""
        return bool(await self._sesion.scalar(
            text("""
                SELECT EXISTS (SELECT FROM player_cards WHERE user_id = :usuario)
                    OR EXISTS (SELECT FROM cube_transactions WHERE user_id = :usuario)
            """),
            {"usuario": usuario_id},
        ))

    async def seleccionar_cartas(self) -> tuple[str, ...]:
        """Sortea las PK de Catálogo y protege su elegibilidad hasta el commit."""
        ids = await self._sesion.scalars(
            text("""
                SELECT c.id
                FROM catalog_cards c JOIN catalog_card_images i ON i.id = c.image_id
                WHERE c.rarity = 'COMUN' AND i.state = 'READY'
                  AND i.original_storage_key ~ '^gridfs:[0-9a-f]{24}$'
                  AND i.thumbnail_storage_key ~ '^gridfs:[0-9a-f]{24}$'
                  AND i.original_storage_key <> i.thumbnail_storage_key
                  AND i.thumbnail_format = 'WEBP'
                ORDER BY random()
                LIMIT :cantidad
                FOR SHARE OF c, i
            """),
            {"cantidad": INITIAL_CARD_COUNT},
        )
        return tuple(ids)

    async def registrar_entrega(self, usuario_id: str, cartas: tuple[str, ...]) -> None:
        """Persiste todos los efectos del premio en la sesión recibida."""
        await self._sesion.execute(
            text("""
                INSERT INTO player_cards (user_id, card_id, quantity)
                VALUES (:usuario, :carta, 1)
            """),
            [{"usuario": usuario_id, "carta": carta} for carta in cartas],
        )
        await self._sesion.execute(
            text("""
                INSERT INTO cube_transactions (id, user_id, amount, balance_after, reason)
                VALUES (:id, :usuario, :cubos, :cubos, :motivo)
            """),
            {
                "id": str(uuid4()), "usuario": usuario_id,
                "cubos": INITIAL_CUBES, "motivo": INITIAL_COLLECTION,
            },
        )
        await self._sesion.execute(
            text("""
                UPDATE player_profiles
                SET cubes = :cubos, has_received_initial_collection = true, updated_at = now()
                WHERE user_id = :usuario
            """),
            {"usuario": usuario_id, "cubos": INITIAL_CUBES},
        )


class SqlUnidadEntregaInicial:
    """Compone la transacción oficial y traduce fallos de persistencia."""

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        crear_autorizacion: Callable[[AsyncSession], AutorizarJugador],
    ) -> None:
        self._factory = factory
        self._crear_autorizacion = crear_autorizacion

    @asynccontextmanager
    async def transaccion(self) -> AsyncIterator[TransaccionEntregaInicial]:
        """Usa una sola sesión para autorización, selección y escritura de beneficios."""
        from src.database.postgresql.connection import transactional_session

        try:
            async with transactional_session(self._factory) as sesion:
                yield SqlTransaccionEntregaInicial(sesion, self._crear_autorizacion(sesion))
        except SQLAlchemyError:
            raise ProvisionNoDisponible("No se pudo confirmar la colección inicial.") from None
