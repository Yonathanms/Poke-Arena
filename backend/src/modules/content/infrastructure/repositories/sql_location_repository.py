from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.application.ports import ILocationRepository
from src.modules.content.domain.entities import Location
from src.modules.content.domain.value_objects import LocationEffectSpec, LocationEffectType
from src.modules.content.infrastructure.models import LocationModel


class SqlLocationRepository(ILocationRepository):
    """Repositorio relacional de ubicaciones utilizando SQLAlchemy 2.0 (PostgreSQL)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, location: Location) -> None:
        effect_dict = {}
        if location.effect:
            effect_dict = {
                "effect_type": location.effect.effect_type.value,
                "description": location.effect.description,
                "params": location.effect.params,
            }

        model = LocationModel(
            id=location.id,
            name=location.name,
            image_url=location.image_url,
            thumbnail_url=location.thumbnail_url,
            effect_spec=effect_dict,
            created_at=location.created_at,
        )
        self.session.add(model)

    async def get_by_id(self, location_id: str) -> Location | None:
        stmt = select(LocationModel).where(LocationModel.id == location_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self) -> list[Location]:
        stmt = select(LocationModel)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model: LocationModel) -> Location:
        raw_effect = model.effect_spec or {}
        raw_type = str(raw_effect.get("effect_type", LocationEffectType.BONIFICACION_PODER.value))
        effect = LocationEffectSpec(
            effect_type=LocationEffectType(raw_type),
            description=str(raw_effect.get("description", "")),
            params=dict(raw_effect.get("params", {})),
        )
        loc = Location.create(
            name=model.name,
            image_url=model.image_url,
            thumbnail_url=model.thumbnail_url,
            effect=effect,
            location_id=model.id,
        )
        loc.created_at = model.created_at
        return loc
