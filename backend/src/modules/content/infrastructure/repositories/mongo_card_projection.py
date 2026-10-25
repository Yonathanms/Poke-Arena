import re
import unicodedata
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from src.modules.content.application.dtos import OutboxClaimDTO
from src.modules.content.application.ports import ICardProjectionWriter, ICardSearchProjectionPort
from src.modules.content.domain.entities import Card


class MongoCardProjection(ICardSearchProjectionPort, ICardProjectionWriter):
    """Adaptador de proyecciones desnormalizadas de catálogo en MongoDB (RNF-ALM-01, US 2.1.2)."""

    COLLECTION_NAME = "cards_projection"

    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self.db = db
        self.collection = self.db[self.COLLECTION_NAME]

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Retorna nombre en minúsculas sin diacríticos para búsqueda insensible a tildes."""
        nfkd = unicodedata.normalize("NFKD", name.lower())
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    async def sync_card_projection(self, card: Card) -> None:
        """Actualiza atómicamente solo si la versión recibida es la más reciente."""
        ability_dict = None
        if card.ability:
            ability_dict = {
                "code": card.ability_code.value if card.ability_code else None,
                "ability_type": card.ability.ability_type.value,
                "description": card.ability.description,
                "params": card.ability.params,
            }

        doc = {
            "_id": card.id,
            "id": card.id,
            "code": card.code,
            "name": card.name,
            "name_normalized": self._normalize_name(card.name),
            "cost": card.cost,
            "power": card.power,
            "card_type": card.card_type.value,
            "rarity": card.rarity.value,
            "image_url": card.image_url,
            "thumbnail_url": card.thumbnail_url,
            "ability": ability_dict,
            "aggregate_version": card.version,
        }
        await self._write_if_newer(card.id, card.version, doc)

    async def project_versioned(self, event: OutboxClaimDTO) -> bool:
        document = dict(event.payload)
        document["_id"] = event.aggregate_id
        document["aggregate_version"] = event.aggregate_version
        # Inyectar name_normalized para búsqueda insensible a diacríticos
        if "name" in document and isinstance(document["name"], str):
            document["name_normalized"] = self._normalize_name(document["name"])
        fields = {key: value for key, value in document.items() if key != "_id"}
        try:
            result = await self.collection.update_one(
                {
                    "_id": event.aggregate_id,
                    "$or": [
                        {"aggregate_version": {"$lt": event.aggregate_version}},
                        {"aggregate_version": {"$exists": False}},
                    ],
                },
                {"$set": fields},
                upsert=True,
            )
            return result.matched_count > 0 or result.upserted_id is not None
        except DuplicateKeyError:
            # A concurrent event already inserted a newer/equal version for this _id.
            return False

    async def _write_if_newer(self, card_id: str, version: int, document: dict[str, Any]) -> None:
        fields = {key: value for key, value in document.items() if key != "_id"}
        try:
            await self.collection.update_one(
                {
                    "_id": card_id,
                    "$or": [
                        {"aggregate_version": {"$lt": version}},
                        {"aggregate_version": {"$exists": False}},
                    ],
                },
                {"$set": fields},
                upsert=True,
            )
        except DuplicateKeyError:
            # Duplicate _id means a concurrent writer has an equal or newer version.
            return

    async def search_cards(
        self,
        name: str | None = None,
        code: str | None = None,
        card_type: str | None = None,
        cost: int | None = None,
        cost_min: int | None = None,
        cost_max: int | None = None,
        power: int | None = None,
        power_min: int | None = None,
        power_max: int | None = None,
        rarity: str | None = None,
        ability_code: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Realiza consultas optimizadas con índices sobre MongoDB."""
        filters: dict[str, Any] = {}

        if name:
            escaped = re.escape(self._normalize_name(name.strip()))
            filters["name_normalized"] = {"$regex": escaped, "$options": "i"}
        if code:
            filters["code"] = code.upper()
        if card_type:
            filters["card_type"] = card_type.upper()
        if rarity:
            filters["rarity"] = rarity.upper()
        if ability_code:
            filters["ability.code"] = ability_code.upper()

        if cost is not None:
            filters["cost"] = cost
        elif cost_min is not None or cost_max is not None:
            cost_filter: dict[str, int] = {}
            if cost_min is not None:
                cost_filter["$gte"] = cost_min
            if cost_max is not None:
                cost_filter["$lte"] = cost_max
            filters["cost"] = cost_filter

        if power is not None:
            filters["power"] = power
        elif power_min is not None or power_max is not None:
            power_filter: dict[str, int] = {}
            if power_min is not None:
                power_filter["$gte"] = power_min
            if power_max is not None:
                power_filter["$lte"] = power_max
            filters["power"] = power_filter

        total = await self.collection.count_documents(filters)
        cursor = (
            self.collection.find(filters, {"_id": 0, "name_normalized": 0})
            .sort("code", 1)
            .skip(skip)
            .limit(limit)
        )
        items = await cursor.to_list(length=limit)

        return items, total
