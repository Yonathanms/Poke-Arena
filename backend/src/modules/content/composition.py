"""Composition Root del módulo Content.

Único lugar del módulo donde se conectan los Puertos (application) con sus
Adaptadores (infrastructure). La capa `presentation` obtiene los casos de uso
ya construidos desde aquí y nunca importa infraestructura directamente.

Si cambia una tecnología (ej. Azure Blob en vez de disco local) o el cableado
de la arquitectura, el cambio se limita a este archivo.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.application.ports import IContentAuthorizationPort
from src.modules.content.application.use_cases.create_card import (
    AuthenticatedCardActor,
    CreateCardUseCase,
)
from src.modules.content.application.use_cases.create_location import CreateLocationUseCase
from src.modules.content.application.use_cases.list_abilities import ListCardAbilitiesUseCase
from src.modules.content.application.use_cases.list_locations import ListLocationsUseCase
from src.modules.content.application.use_cases.process_durable_work import (
    GetCardImageStatusUseCase,
)
from src.modules.content.application.use_cases.search_cards import SearchCardsUseCase
from src.modules.content.infrastructure.identity_authorization import (
    IdentityContentAuthorizationAdapter,
)
from src.modules.content.infrastructure.repositories.mongo_card_projection import (
    MongoCardProjection,
)
from src.modules.content.infrastructure.repositories.sql_ability_repository import (
    SqlAbilityRepository,
)
from src.modules.content.infrastructure.repositories.sql_card_code_allocator import (
    SqlCardCodeAllocator,
)
from src.modules.content.infrastructure.repositories.sql_card_image_repository import (
    SqlCardImageRepository,
)
from src.modules.content.infrastructure.repositories.sql_card_repository import (
    SqlCardRepository,
)
from src.modules.content.infrastructure.repositories.sql_creation_records import (
    SqlCardCreationIdempotencyAdapter,
    SqlOutboxWriter,
)
from src.modules.content.infrastructure.repositories.sql_location_repository import (
    SqlLocationRepository,
)
from src.modules.content.infrastructure.repositories.sql_processing_transactions import (
    SqlCardImageProcessingTransactions,
)
from src.modules.content.infrastructure.services.pillow_image_processor import (
    PillowImageProcessor,
)
from src.modules.content.infrastructure.unit_of_work import SqlUnitOfWork
from src.modules.identity.contracts import (
    IdentityServiceUnavailableError,
    InvalidAccessTokenError,
)
from src.shared.application.ports import IIdempotencyService
from src.shared.infrastructure.database import (
    AsyncWriteSessionLocal,
    get_read_db,
    get_write_db,
)
from src.shared.infrastructure.idempotency import IdempotencyService
from src.shared.infrastructure.mongo import get_mongo_db
from src.shared.infrastructure.storage import get_file_storage

platform_bearer = HTTPBearer(auto_error=False, scheme_name="PlatformBearerAuth")


def get_content_authorization_port(request: Request) -> IContentAuthorizationPort:
    identity_contract = getattr(request.app.state, "identity_module_contract", None)
    if identity_contract is None:
        raise IdentityServiceUnavailableError()
    return IdentityContentAuthorizationAdapter(identity_contract)


async def get_authenticated_card_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(platform_bearer),
) -> AuthenticatedCardActor:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere una credencial Bearer válida.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        principal = await get_content_authorization_port(request).authenticate(
            credentials.credentials
        )
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La credencial de plataforma no es válida o expiró.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except IdentityServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de autenticación no está disponible.",
        ) from exc
    if not principal.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere permiso de administrador de plataforma.",
        )
    if not principal.actor_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identity no proporcionó un identificador de actor válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthenticatedCardActor(actor_id=principal.actor_id)


@dataclass(frozen=True)
class CardPersistenceAdapters:
    """Adaptadores de escritura de Carta sobre una única sesión/UoW."""

    uow: SqlUnitOfWork
    card_repository: SqlCardRepository
    code_allocator: SqlCardCodeAllocator
    ability_repository: SqlAbilityRepository
    image_repository: SqlCardImageRepository


def build_card_persistence_adapters(session: AsyncSession) -> CardPersistenceAdapters:
    """Construye todos los adaptadores transaccionales sobre la misma sesión."""
    return CardPersistenceAdapters(
        uow=SqlUnitOfWork(session),
        card_repository=SqlCardRepository(session),
        code_allocator=SqlCardCodeAllocator(session),
        ability_repository=SqlAbilityRepository(session),
        image_repository=SqlCardImageRepository(session),
    )


def get_create_card_use_case(
    db: AsyncSession = Depends(get_write_db),
) -> CreateCardUseCase:
    """Escritura: requiere WriteSession (Master SQL) - Regla 5."""
    persistence = build_card_persistence_adapters(db)
    return CreateCardUseCase(
        uow=persistence.uow,
        card_repo=persistence.card_repository,
        code_allocator=persistence.code_allocator,
        ability_repo=persistence.ability_repository,
        image_repo=persistence.image_repository,
        idempotency=SqlCardCreationIdempotencyAdapter(db, AsyncWriteSessionLocal),
        outbox=SqlOutboxWriter(db),
        image_inspector=PillowImageProcessor(),
        file_storage=get_file_storage(),
    )


def get_list_card_abilities_use_case(
    db: AsyncSession = Depends(get_write_db),
) -> ListCardAbilitiesUseCase:
    """Lee el catálogo de habilidades vigente desde el primario PostgreSQL."""
    return ListCardAbilitiesUseCase(SqlAbilityRepository(db))


def get_card_image_status_use_case() -> GetCardImageStatusUseCase:
    """Consulta el estado actual usando siempre el primario PostgreSQL."""
    return GetCardImageStatusUseCase(
        SqlCardImageProcessingTransactions(AsyncWriteSessionLocal)
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
    db: AsyncSession = Depends(get_write_db),
) -> ListLocationsUseCase:
    """Lectura desde el primario SQL.
    Dev: la réplica (puerto 5433) es un contenedor independiente sin streaming
    replication, por lo que los datos escritos al maestro nunca llegan ahí.
    RNF-DIS-02 se demuestra con la proyección MongoDB del catálogo de cartas.
    """
    return ListLocationsUseCase(SqlLocationRepository(db))


def get_idempotency_service(
    db: AsyncSession = Depends(get_write_db),
) -> IIdempotencyService:
    """Servicio de idempotencia conectado a la sesión de escritura."""
    return IdempotencyService(db)
