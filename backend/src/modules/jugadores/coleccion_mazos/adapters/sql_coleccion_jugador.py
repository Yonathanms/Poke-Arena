"""Adaptador SQL de lectura para la colección de cartas del jugador."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.entrega_inicial_model import CartaColeccion

_SQL_LISTAR_COLECCION = text("""
    SELECT c.id, c.code, c.name, c.card_type, c.rarity, pc.quantity
    FROM player_cards pc
    JOIN catalog_cards c ON c.id = pc.card_id
    WHERE pc.user_id = :user_id
    ORDER BY c.card_type, c.name
""")


class SqlColeccionJugador:
    """Lee la colección personal del jugador desde PostgreSQL."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def listar_cartas(self, usuario_id: str) -> list[CartaColeccion]:
        """Consulta las cartas pertenecientes al jugador autenticado."""
        async with self._factory() as sesion:
            filas = await sesion.execute(_SQL_LISTAR_COLECCION, {"user_id": usuario_id})
            return [
                CartaColeccion(
                    id=fila[0],
                    code=fila[1],
                    name=fila[2],
                    card_type=fila[3],
                    rarity=fila[4],
                    quantity=int(fila[5]),
                )
                for fila in filas
            ]
