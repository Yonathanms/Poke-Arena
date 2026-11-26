"""Adaptador SQL de lectura autoritativa de cartas para reconciliación con MongoDB."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.proyeccion_carta import FuenteSqlTemporal, ProyeccionCarta
from .cartas_orm import CartaORM, HabilidadORM, ImagenCartaORM


class SqlFuenteCartas:
    """Lee el estado autoritativo de catalog_cards en transacciones breves."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        """Recibe la fábrica oficial de sesiones PostgreSQL."""
        self._factory = factory

    async def listar_cartas_listas(self) -> list[ProyeccionCarta]:
        """Consulta todas las cartas confirmadas con imagen en estado READY."""
        try:
            async with self._factory() as sesion:
                filas = (
                    await sesion.execute(
                        select(
                            CartaORM,
                            HabilidadORM.code,
                            HabilidadORM.name,
                            ImagenCartaORM.state,
                        )
                        .join(HabilidadORM, HabilidadORM.id == CartaORM.ability_id)
                        .join(ImagenCartaORM, ImagenCartaORM.id == CartaORM.image_id)
                        .where(
                            CartaORM.image_id.is_not(None),
                            ImagenCartaORM.state == "READY",
                        )
                        .order_by(CartaORM.code)
                    )
                ).all()
        except SQLAlchemyError:
            raise FuenteSqlTemporal("postgresql_no_disponible") from None

        proyecciones: list[ProyeccionCarta] = []
        for carta, ability_code, ability_name, image_state in filas:
            campos = {
                "id": carta.id,
                "code": carta.code,
                "name": carta.name,
                "card_type": carta.card_type,
                "rarity": carta.rarity,
                "cost": carta.cost,
                "power": carta.power,
                "ability_id": carta.ability_id,
                "ability_code": ability_code,
                "ability_name": ability_name,
                "image_id": carta.image_id,
                "image_status": image_state,
            }
            proyecciones.append(ProyeccionCarta(carta.id, int(carta.version), campos))
        return proyecciones
