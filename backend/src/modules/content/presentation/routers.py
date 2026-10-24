import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.modules.content.application.use_cases.create_card import (
    AuthenticatedCardActor,
    CreateCardCommand,
    CreateCardUseCase,
)
from src.modules.content.application.use_cases.create_location import (
    CreateLocationCommand,
    CreateLocationUseCase,
)
from src.modules.content.application.use_cases.list_abilities import ListCardAbilitiesUseCase
from src.modules.content.application.use_cases.list_locations import ListLocationsUseCase
from src.modules.content.application.use_cases.process_durable_work import (
    GetCardImageStatusUseCase,
)
from src.modules.content.application.use_cases.search_cards import (
    SearchCardsQuery,
    SearchCardsUseCase,
)
from src.modules.content.composition import (
    get_authenticated_card_actor,
    get_card_image_status_use_case,
    get_create_card_use_case,
    get_create_location_use_case,
    get_idempotency_service,
    get_list_card_abilities_use_case,
    get_list_locations_use_case,
    get_search_cards_use_case,
)
from src.modules.content.domain.entities import Location
from src.modules.content.domain.exceptions import CardNotFoundError
from src.modules.content.domain.value_objects import (
    AbilityCode,
    CardRarity,
    CardType,
    LocationEffectSpec,
    LocationEffectType,
)
from src.modules.content.presentation.schemas import (
    CardAbilitySummaryResponse,
    CardCreatedResponse,
    CardImageStatusResponse,
    LocationResponse,
    SearchCardsResponse,
)
from src.shared.application.ports import IIdempotencyService

content_router = APIRouter(prefix="/content")


def _location_to_response(location: Location) -> LocationResponse:
    return LocationResponse(
        id=location.id,
        name=location.name,
        image_url=location.image_url,
        thumbnail_url=location.thumbnail_url,
        effect=(
            {
                "effect_type": location.effect.effect_type,
                "description": location.effect.description,
                "params": location.effect.params,
            }
            if location.effect
            else None
        ),
    )


# ------------------------------------------------------------------------------
# 1. Crear Carta (F-02 / US 2.1.1 - Requiere WriteSession)
# ------------------------------------------------------------------------------
@content_router.post(
    "/cards",
    response_model=CardCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Cards"],
    summary="Crear una nueva carta en el catálogo",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Solicitud malformada."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Credencial ausente o inválida."},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere permiso de administrador."},
        status.HTTP_409_CONFLICT: {"description": "Conflicto de idempotencia o capacidad."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Campos o archivo inválidos."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Error interno sanitizado."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Identity, PostgreSQL o almacenamiento no disponibles."
        },
    },
)
async def create_card(
    request: Request,
    response: Response,
    name: Annotated[str, Form(description="Nombre del Pokémon")],
    cost: Annotated[int, Form(description="Costo de energía [0..10]")],
    power: Annotated[int, Form(description="Poder de la carta")],
    card_type: Annotated[CardType, Form(description="Tipo elemental")],
    rarity: Annotated[CardRarity, Form(description="Rareza")],
    ability_code: Annotated[str, Form()],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    image: Annotated[
        UploadFile | None, File(description="Imagen opcional; se integrará en V2")
    ] = None,
    actor: AuthenticatedCardActor = Depends(get_authenticated_card_actor),
    use_case: CreateCardUseCase = Depends(get_create_card_use_case),
) -> CardCreatedResponse:
    allowed_fields = {
        "name",
        "cost",
        "power",
        "card_type",
        "rarity",
        "image",
        "ability_code",
    }
    unexpected_fields = set((await request.form()).keys()) - allowed_fields
    if unexpected_fields:
        raise RequestValidationError(
            [
                {
                    "loc": ("body", field),
                    "msg": "Campo no permitido por el contrato de Crear Carta.",
                    "type": "extra_forbidden",
                }
                for field in sorted(unexpected_fields)
            ]
        )
    image_bytes = await image.read() if image is not None else None
    result = await use_case.execute(
        CreateCardCommand(
            name=name,
            cost=cost,
            power=power,
            card_type=card_type,
            rarity=rarity,
            ability_code=AbilityCode(ability_code),
            image_bytes=image_bytes,
            actor=actor,
            idempotency_key=idempotency_key,
        )
    )
    response.headers["Location"] = result.snapshot.status_url
    return CardCreatedResponse.model_validate(result.snapshot.as_json())


@content_router.get(
    "/abilities",
    response_model=list[CardAbilitySummaryResponse],
    status_code=status.HTTP_200_OK,
    tags=["Cards"],
    summary="Listar habilidades seleccionables al crear una carta",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Credencial ausente o inválida."},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere permiso de administrador."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Identity o PostgreSQL no disponibles."
        },
    },
)
async def list_card_abilities(
    _actor: AuthenticatedCardActor = Depends(get_authenticated_card_actor),
    use_case: ListCardAbilitiesUseCase = Depends(get_list_card_abilities_use_case),
) -> list[CardAbilitySummaryResponse]:
    abilities = await use_case.execute()
    return [
        CardAbilitySummaryResponse(
            code=ability.code,
            name=ability.name,
            trigger=ability.trigger,
            effect=ability.effect,
            affected_card_type=ability.affected_card_type,
            parameters=ability.parameters,
        )
        for ability in abilities
    ]


@content_router.get(
    "/cards/{card_id}/image-status",
    response_model=CardImageStatusResponse,
    status_code=status.HTTP_200_OK,
    tags=["Cards"],
    summary="Consultar el estado actual de las imágenes de una carta",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Credencial ausente o inválida."},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere permiso de administrador."},
        status.HTTP_404_NOT_FOUND: {"description": "La carta no existe."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Identity o PostgreSQL no disponibles."
        },
    },
)
async def get_card_image_status(
    card_id: UUID,
    _actor: AuthenticatedCardActor = Depends(get_authenticated_card_actor),
    use_case: GetCardImageStatusUseCase = Depends(get_card_image_status_use_case),
) -> CardImageStatusResponse:
    result = await use_case.execute(str(card_id))
    if result is None:
        raise CardNotFoundError(str(card_id))
    return CardImageStatusResponse.model_validate(result.__dict__)


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
    use_case: SearchCardsUseCase = Depends(get_search_cards_use_case),
) -> Any:
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
        items=result.items,
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
    use_case: CreateLocationUseCase = Depends(get_create_location_use_case),
    idempotency_service: IIdempotencyService = Depends(get_idempotency_service),
) -> Any:
    if idempotency_key:
        cached = await idempotency_service.get_recorded_response(
            idempotency_key, "/api/v1/content/locations"
        )
        if cached:
            return JSONResponse(content=cached["body"], status_code=cached["status_code"])

    image_bytes = await image.read()
    params = json.loads(effect_params_json) if effect_params_json else {}

    effect = LocationEffectSpec(
        effect_type=effect_type,
        description=effect_description,
        params=params,
    )

    location = await use_case.execute(
        CreateLocationCommand(
            name=name,
            effect=effect,
            image_bytes=image_bytes,
        )
    )
    response_dto = _location_to_response(location)

    if idempotency_key:
        await idempotency_service.record_response(
            idempotency_key,
            "/api/v1/content/locations",
            status.HTTP_201_CREATED,
            response_dto.model_dump(),
        )

    return response_dto


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
    use_case: ListLocationsUseCase = Depends(get_list_locations_use_case),
) -> Any:
    locations = await use_case.execute()
    return [_location_to_response(loc) for loc in locations]
