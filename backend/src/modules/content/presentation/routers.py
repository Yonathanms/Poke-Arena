import json
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    UploadFile,
    status,
)
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content.application.use_cases.create_card import (
    CreateCardCommand,
    CreateCardUseCase,
)
from src.modules.content.application.use_cases.create_location import (
    CreateLocationCommand,
    CreateLocationUseCase,
)
from src.modules.content.application.use_cases.search_cards import (
    SearchCardsQuery,
    SearchCardsUseCase,
)
from src.modules.content.domain.value_objects import (
    AbilitySpec,
    AbilityType,
    CardRarity,
    CardType,
    LocationEffectSpec,
    LocationEffectType,
)
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
from src.modules.content.presentation.schemas import (
    CardResponse,
    LocationResponse,
    SearchCardsResponse,
)
from src.shared.infrastructure.database import get_read_db, get_write_db
from src.shared.infrastructure.mongo import get_mongo_db
from src.shared.infrastructure.storage import get_file_storage

content_router = APIRouter(prefix="/content")


# ------------------------------------------------------------------------------
# 1. Crear Carta (F-02 / US 2.1.1 - Requiere WriteSession)
# ------------------------------------------------------------------------------
@content_router.post(
    "/cards",
    response_model=CardResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Cards"],
    summary="Crear una nueva carta en el catálogo",
)
async def create_card(
    code: Annotated[str, Form(description="Código oficial ej: PKA-FUE-001")],
    name: Annotated[str, Form(description="Nombre del Pokémon")],
    cost: Annotated[int, Form(description="Costo de energía [1..6]")],
    power: Annotated[int, Form(description="Poder de la carta")],
    card_type: Annotated[CardType, Form(description="Tipo elemental")],
    rarity: Annotated[CardRarity, Form(description="Rareza")],
    image: Annotated[UploadFile, File(description="Imagen proporción 5:7")],
    ability_type: Annotated[AbilityType | None, Form()] = None,
    ability_description: Annotated[str | None, Form()] = None,
    ability_params_json: Annotated[str | None, Form()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_write_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> Any:
    image_bytes = await image.read()

    ability: AbilitySpec | None = None
    if ability_type and ability_type != AbilityType.NINGUNA:
        params = json.loads(ability_params_json) if ability_params_json else {}
        ability = AbilitySpec(
            ability_type=ability_type,
            description=ability_description or "",
            params=params,
        )

    uow = SqlUnitOfWork(db)
    card_repo = SqlCardRepository(db)
    projection_port = MongoCardProjection(mongo_db)
    image_processor = PillowImageProcessor()
    storage = get_file_storage()

    use_case = CreateCardUseCase(
        uow=uow,
        card_repo=card_repo,
        projection_port=projection_port,
        image_processor=image_processor,
        file_storage=storage,
    )

    card = await use_case.execute(
        CreateCardCommand(
            code=code,
            name=name,
            cost=cost,
            power=power,
            card_type=card_type,
            rarity=rarity,
            image_bytes=image_bytes,
            ability=ability,
        )
    )

    ability_schema = None
    if card.ability:
        ability_schema = {
            "ability_type": card.ability.ability_type,
            "description": card.ability.description,
            "params": card.ability.params,
        }

    return CardResponse(
        id=card.id,
        code=card.code,
        name=card.name,
        cost=card.cost,
        power=card.power,
        card_type=card.card_type,
        rarity=card.rarity,
        image_url=card.image_url,
        thumbnail_url=card.thumbnail_url,
        ability=ability_schema,
    )


# ------------------------------------------------------------------------------
# 2. Buscar Cartas (US 2.1.2 - Proyecciones de lectura rápida en MongoDB)
# ------------------------------------------------------------------------------
@content_router.get(
    "/cards",
    response_model=SearchCardsResponse,
    status_code=status.HTTP_200_OK,
    tags=["Cards"],
    summary="Buscar cartas en el catálogo con filtros",
)
async def search_cards(
    name: Annotated[str | None, Query(description="Filtrar por nombre")] = None,
    card_type: Annotated[str | None, Query(description="Filtrar por tipo elemental")] = None,
    cost: Annotated[int | None, Query(description="Filtrar por costo")] = None,
    rarity: Annotated[str | None, Query(description="Filtrar por rareza")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> Any:
    projection_port = MongoCardProjection(mongo_db)
    use_case = SearchCardsUseCase(projection_port)

    result = await use_case.execute(
        SearchCardsQuery(
            name=name,
            card_type=card_type,
            cost=cost,
            rarity=rarity,
            skip=skip,
            limit=limit,
        )
    )

    return SearchCardsResponse(
        items=result.items,  # type: ignore[arg-type]
        total=result.total,
        skip=result.skip,
        limit=result.limit,
    )


# ------------------------------------------------------------------------------
# 3. Crear Ubicación de Juego (F-03 / US 2.1.3 - Requiere WriteSession)
# ------------------------------------------------------------------------------
@content_router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Locations"],
    summary="Crear una nueva ubicación de juego",
)
async def create_location(
    name: Annotated[str, Form(description="Nombre del lugar")],
    effect_type: Annotated[LocationEffectType, Form(description="Tipo de efecto")],
    effect_description: Annotated[str, Form(description="Descripción del efecto")],
    image: Annotated[UploadFile, File(description="Imagen proporción 4:3")],
    effect_params_json: Annotated[str | None, Form()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_write_db),
) -> Any:
    image_bytes = await image.read()
    params = json.loads(effect_params_json) if effect_params_json else {}

    effect = LocationEffectSpec(
        effect_type=effect_type,
        description=effect_description,
        params=params,
    )

    uow = SqlUnitOfWork(db)
    location_repo = SqlLocationRepository(db)
    image_processor = PillowImageProcessor()
    storage = get_file_storage()

    use_case = CreateLocationUseCase(
        uow=uow,
        location_repo=location_repo,
        image_processor=image_processor,
        file_storage=storage,
    )

    location = await use_case.execute(
        CreateLocationCommand(
            name=name,
            effect=effect,
            image_bytes=image_bytes,
        )
    )

    return LocationResponse(
        id=location.id,
        name=location.name,
        image_url=location.image_url,
        thumbnail_url=location.thumbnail_url,
        effect={
            "effect_type": location.effect.effect_type,
            "description": location.effect.description,
            "params": location.effect.params,
        },
    )


# ------------------------------------------------------------------------------
# 4. Listar Ubicaciones (Demuestra ReadSession / Réplica SQL - RNF-DIS-02)
# ------------------------------------------------------------------------------
@content_router.get(
    "/locations",
    response_model=list[LocationResponse],
    status_code=status.HTTP_200_OK,
    tags=["Locations"],
    summary="Listar ubicaciones disponibles (consulta servida desde réplica)",
)
async def list_locations(
    db: AsyncSession = Depends(get_read_db),
) -> Any:
    location_repo = SqlLocationRepository(db)
    locations = await location_repo.list_all()
    return [
        LocationResponse(
            id=loc.id,
            name=loc.name,
            image_url=loc.image_url,
            thumbnail_url=loc.thumbnail_url,
            effect={
                "effect_type": loc.effect.effect_type,
                "description": loc.effect.description,
                "params": loc.effect.params,
            },
        )
        for loc in locations
    ]
