import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.modules.content.application.ports import ICardSearchProjectionPort
from src.modules.content.domain.entities import Card


class MongoCardProjection(ICardSearchProjectionPort):
    """Adaptador de proyecciones desnormalizadas de catálogo en MongoDB (RNF-ALM-01, US 2.1.2)."""

    COLLECTION_NAME = "cards_projection"

    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self.db = db
        self.collection = self.db[self.COLLECTION_NAME]

    async def sync_card_projection(self, card: Card) -> None:
        """Inserta o actualiza el documento de proyección para búsquedas inmediatas sin joins."""
        ability_dict = None
        if card.ability:
            ability_dict = {
                "ability_type": card.ability.ability_type.value,
                "description": card.ability.description,
                "params": card.ability.params,
            }

        doc = {
            "_id": card.id,
            "id": card.id,
            "code": card.code,
            "name": card.name,
            "cost": card.cost,
            "power": card.power,
            "card_type": card.card_type.value,
            "rarity": card.rarity.value,
            "image_url": card.image_url,
            "thumbnail_url": card.thumbnail_url,
            "ability": ability_dict,
        }

        await self.collection.replace_one({"_id": card.id}, doc, upsert=True)

    async def search_cards(
        self,
        name: str | None = None,
        card_type: str | None = None,
        cost: int | None = None,
        rarity: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Realiza consultas optimizadas con índices sobre MongoDB."""
        filters: dict[str, Any] = {}

        if name:
            escaped_name = re.escape(name.strip())
            filters["name"] = {"$regex": escaped_name, "$options": "i"}
        if card_type:
            filters["card_type"] = card_type.upper()
        if cost is not None:
            filters["cost"] = cost
        if rarity:
            filters["rarity"] = rarity.upper()

        total = await self.collection.count_documents(filters)
        cursor = self.collection.find(filters, {"_id": 0}).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)

        return items, total
