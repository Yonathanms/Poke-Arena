"""Composition Root del módulo Content.

Único lugar del módulo donde se conectan los Puertos (application) con sus
Adaptadores (infrastructure). La capa `presentation` obtiene los casos de uso
ya construidos desde aquí y nunca importa infraestructura directamente.

Si cambia una tecnología (ej. Azure Blob en vez de disco local) o el cableado
de la arquitectura, el cambio se limita a este archivo.
"""

from typing import Any

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.application.use_cases.create_card import CreateCardUseCase
from src.modules.content.application.use_cases.create_location import CreateLocationUseCase
from src.modules.content.application.use_cases.list_locations import ListLocationsUseCase
from src.modules.content.application.use_cases.search_cards import SearchCardsUseCase
from src.modules.content.infrastructure.repositories.mongo_card_projection import (
    MongoCardProjection,
)
from src.modules.content.infrastructure.repositories.sql_card_repository import (
    SqlCardRepository,
)
from src.modules.content.infrastructure.repositories.sql_location_repository import (
    SqlLocationRepository,
)
from src.modules.content.infrastructure.services.pillow_image_processor import (
    PillowImageProcessor,
)
from src.modules.content.infrastructure.unit_of_work import SqlUnitOfWork
from src.shared.application.ports import IIdempotencyService
from src.shared.infrastructure.database import get_read_db, get_write_db
from src.shared.infrastructure.idempotency import IdempotencyService
from src.shared.infrastructure.mongo import get_mongo_db
from src.shared.infrastructure.storage import get_file_storage


def get_create_card_use_case(
    db: AsyncSession = Depends(get_write_db),
    mongo_db: AsyncIOMotorDatabase[Any] = Depends(get_mongo_db),
) -> CreateCardUseCase:
    """Escritura: requiere WriteSession (Master SQL) - Regla 5."""
    return CreateCardUseCase(
        uow=SqlUnitOfWork(db),
        card_repo=SqlCardRepository(db),
        projection_port=MongoCardProjection(mongo_db),
        image_processor=PillowImageProcessor(),
        file_storage=get_file_storage(),
    )


def get_search_cards_use_case(
    mongo_db: AsyncIOMotorDatabase[Any] = Depends(get_mongo_db),
) -> SearchCardsUseCase:
    """Lectura: proyección NoSQL sin joins (RNF-ALM-01)."""
    return SearchCardsUseCase(MongoCardProjection(mongo_db))


def get_create_location_use_case(
    db: AsyncSession = Depends(get_write_db),
) -> CreateLocationUseCase:
    """Escritura: requiere WriteSession (Master SQL) - Regla 5."""
    return CreateLocationUseCase(
        uow=SqlUnitOfWork(db),
        location_repo=SqlLocationRepository(db),
        image_processor=PillowImageProcessor(),
        file_storage=get_file_storage(),
    )


def get_list_locations_use_case(
    db: AsyncSession = Depends(get_read_db),
) -> ListLocationsUseCase:
    """Lectura: ReadSession (Réplica SQL) - RNF-DIS-02."""
    return ListLocationsUseCase(SqlLocationRepository(db))


def get_idempotency_service(
    db: AsyncSession = Depends(get_write_db),
) -> IIdempotencyService:
    """Servicio de idempotencia conectado a la sesión de escritura."""
    return IdempotencyService(db)
