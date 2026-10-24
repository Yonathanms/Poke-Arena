import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.modules.identity.application.service import GoogleLoginResult
from src.modules.identity.composition import get_identity_application_service
from src.modules.identity.contracts import (
    IdentityServiceUnavailableError,
    InvalidGoogleCredentialError,
)
from src.modules.identity.domain.value_objects import PlatformRole


class FakeIdentityLoginService:
    async def login_with_google(self, credential: str) -> GoogleLoginResult:
        if credential == "invalid":
            raise InvalidGoogleCredentialError()
        if credential == "unavailable":
            raise IdentityServiceUnavailableError()
        return GoogleLoginResult(
            user_id="00000000-0000-0000-0000-000000000001",
            role=PlatformRole.PLATFORM_ADMIN,
            access_token="opaque-platform-token",
            expires_in=900,
        )

    async def logout(self, access_token: str) -> None:
        return None

    async def login_with_test_identity(self, user_id: str = "local-admin") -> GoogleLoginResult:
        return GoogleLoginResult(
            user_id=user_id,
            role=PlatformRole.PLATFORM_ADMIN,
            access_token="local-platform-token",
            expires_in=900,
            provider="TEST",
        )


@pytest.mark.asyncio
async def test_google_login_returns_platform_bearer_credential() -> None:
    app.dependency_overrides[get_identity_application_service] = lambda: FakeIdentityLoginService()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/identity/google/session",
                json={"google_id_token": "valid-google-token"},
            )
    finally:
        app.dependency_overrides.pop(get_identity_application_service, None)

    assert response.status_code == 201
    assert response.json() == {
        "access_token": "opaque-platform-token",
        "token_type": "Bearer",
        "expires_in": 900,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "role": "PLATFORM_ADMIN",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("credential", "expected_status"), [("invalid", 401), ("unavailable", 503)]
)
async def test_google_login_maps_provider_errors(credential: str, expected_status: int) -> None:
    app.dependency_overrides[get_identity_application_service] = lambda: FakeIdentityLoginService()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/identity/google/session",
                json={"google_id_token": credential},
            )
    finally:
        app.dependency_overrides.pop(get_identity_application_service, None)

    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_logout_revokes_current_session_and_returns_no_content() -> None:
    app.dependency_overrides[get_identity_application_service] = lambda: FakeIdentityLoginService()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/identity/session",
                headers={"Authorization": "Bearer platform-token"},
            )
    finally:
        app.dependency_overrides.pop(get_identity_application_service, None)

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_logout_requires_platform_bearer_credential() -> None:
    app.dependency_overrides[get_identity_application_service] = lambda: FakeIdentityLoginService()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/identity/session")
    finally:
        app.dependency_overrides.pop(get_identity_application_service, None)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_local_test_session_rejects_client_role_and_returns_fixed_admin() -> None:
    app.dependency_overrides[get_identity_application_service] = lambda: FakeIdentityLoginService()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/identity/test-session", json={"user_id": "local-e2e"}
            )
            role_attempt = await client.post(
                "/api/v1/identity/test-session",
                json={"user_id": "local-e2e", "role": "PLATFORM_ADMIN"},
            )
    finally:
        app.dependency_overrides.pop(get_identity_application_service, None)

    assert response.status_code == 201
    assert response.json()["role"] == "PLATFORM_ADMIN"
    assert role_attempt.status_code == 422
