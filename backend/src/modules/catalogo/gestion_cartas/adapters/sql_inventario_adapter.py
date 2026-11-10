"""Adaptador PostgreSQL para consultar el inventario de cartas del jugador (player_cards)."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.postgresql.connection import AsyncSessionLocal

from ..ports.cartas_ports import IInventarioJugadorPort


class SqlInventarioJugadorAdapter(IInventarioJugadorPort):
    """Consulta las cartas poseídas por un jugador en la tabla relacional player_cards."""

    def __init__(self, session_factory: Callable[[], AsyncSession] = AsyncSessionLocal) -> None:
        self._session_factory = session_factory

    async def obtener_cantidades_por_usuario(self, user_id: str) -> dict[str, int]:
        """Devuelve un mapa {card_id: quantity} con las cartas que posee el jugador."""
        if not user_id:
            return {}
        try:
            async with self._session_factory() as session:
                resultado = await session.execute(
                    text("SELECT card_id, quantity FROM player_cards WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
                filas = resultado.fetchall()
                return {str(fila[0]): int(fila[1]) for fila in filas}
        except Exception:
            # Resiliencia: si la base relacional está degradada, devolvemos inventario vacío
            return {}

