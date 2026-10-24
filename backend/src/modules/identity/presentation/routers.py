"""Identity HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.modules.identity.application.service import IdentityApplicationService
from src.modules.identity.composition import get_identity_application_service
from src.modules.identity.contracts import (
    IdentityServiceUnavailableError,
    InvalidGoogleCredentialError,
)
from src.modules.identity.presentation.schemas import (
    GoogleLoginRequest,
    LocalTestLoginRequest,
    PlatformSessionResponse,
)

identity_router = APIRouter(prefix="/identity", tags=["Identity"])
local_test_identity_router = APIRouter(prefix="/identity", tags=["Identity (local)"])
platform_bearer = HTTPBearer(auto_error=False, scheme_name="PlatformBearerAuth")


@identity_router.post(
    "/google/session",
    response_model=PlatformSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Intercambiar una credencial Google por una sesión de Poké-Arena",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Credencial de Google inválida."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Identity, Google o PostgreSQL no disponibles."
        },
    },
)
async def create_google_session(
    payload: GoogleLoginRequest,
    service: Annotated[IdentityApplicationService, Depends(get_identity_application_service)],
) -> PlatformSessionResponse:
    try:
        result = await service.login_with_google(payload.google_id_token)
    except InvalidGoogleCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La credencial de Google no es válida para Poké-Arena.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except IdentityServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de Identity no está disponible.",
        ) from exc
    return PlatformSessionResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user_id=result.user_id,
        role=result.role,
    )


@local_test_identity_router.post(
    "/test-session",
    response_model=PlatformSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear sesión administrativa local para desarrollo y pruebas",
    include_in_schema=False,
)
async def create_local_test_session(
    payload: LocalTestLoginRequest,
    service: Annotated[IdentityApplicationService, Depends(get_identity_application_service)],
) -> PlatformSessionResponse:
    try:
        result = await service.login_with_test_identity(payload.user_id)
    except InvalidGoogleCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado.",
        ) from exc
    except IdentityServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de Identity no está disponible.",
        ) from exc
    return PlatformSessionResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user_id=result.user_id,
        role=result.role,
    )


@identity_router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar la sesión de plataforma actual",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Credencial ausente."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Identity o PostgreSQL no disponibles."
        },
    },
)
async def revoke_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(platform_bearer),
    service: IdentityApplicationService = Depends(get_identity_application_service),
) -> Response:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere una credencial Bearer para cerrar la sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        await service.logout(credentials.credentials)
    except IdentityServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de Identity no está disponible.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
