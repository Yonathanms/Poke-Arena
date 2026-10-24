"""Registro del contrato público de Identity en la composición FastAPI."""

from typing import cast

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.identity.application.service import IdentityApplicationService
from src.modules.identity.contracts import (
    IdentityServiceUnavailableError,
    IIdentityModuleContract,
)
from src.modules.identity.infrastructure.google_identity_provider import GoogleIdentityProvider
from src.modules.identity.infrastructure.opaque_access_token_factory import (
    OpaqueAccessTokenFactory,
)
from src.modules.identity.infrastructure.sql_identity_persistence import SqlIdentityPersistence
from src.shared.infrastructure.config import Settings, get_settings
from src.shared.infrastructure.database import AsyncWriteSessionLocal


def build_identity_application_service(
    session_factory: async_sessionmaker[AsyncSession] = AsyncWriteSessionLocal,
    settings: Settings | None = None,
) -> IdentityApplicationService:
    configuration = settings or get_settings()
    return IdentityApplicationService(
        google_provider=GoogleIdentityProvider(configuration.GOOGLE_OAUTH_CLIENT_ID),
        persistence=SqlIdentityPersistence(session_factory),
        token_factory=OpaqueAccessTokenFactory(),
        platform_admin_subjects=configuration.platform_admin_google_subjects,
        access_token_ttl_seconds=configuration.IDENTITY_ACCESS_TOKEN_TTL_SECONDS,
        allow_test_identity=configuration.ENVIRONMENT.lower() in {"development", "test"},
    )


def register_identity_module(app: FastAPI, identity: IIdentityModuleContract | None) -> None:
    """Registra el proveedor verificador para que otros módulos consuman su contrato."""
    app.state.identity_module_contract = identity
    app.state.identity_application_service = identity


def get_identity_application_service(request: Request) -> IdentityApplicationService:
    service = getattr(request.app.state, "identity_application_service", None)
    if service is None:
        raise IdentityServiceUnavailableError()
    return cast(IdentityApplicationService, service)
