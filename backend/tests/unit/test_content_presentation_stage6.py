"""FastAPI contract checks for the Create Card presentation integration."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.modules.content.application.dtos import CardCreationSnapshot, CreateCardResult
from src.modules.content.composition import (
    get_card_image_status_use_case,
    get_create_card_use_case,
)
from src.modules.identity.composition import register_identity_module
from src.modules.identity.contracts import (
    AuthenticatedPrincipal,
    InvalidAccessTokenError,
)


def test_create_and_status_operations_publish_bearer_security() -> None:
    schema = app.openapi()
    security_scheme = schema["components"]["securitySchemes"]["PlatformBearerAuth"]

    assert security_scheme["type"] == "http"
    assert security_scheme["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/content/cards"]["post"]["security"] == [
        {"PlatformBearerAuth": []}
    ]
    assert schema["paths"]["/api/v1/content/cards/{card_id}/image-status"]["get"][
        "security"
    ] == [{"PlatformBearerAuth": []}]
    assert schema["paths"]["/api/v1/content/abilities"]["get"]["security"] == [
        {"PlatformBearerAuth": []}
    ]


@pytest.mark.asyncio
async def test_status_endpoint_returns_401_without_platform_credentials() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/content/cards/{uuid4()}/image-status")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_status_endpoint_stays_closed_when_identity_is_not_integrated() -> None:
    previous = getattr(app.state, "identity_module_contract", None)
    register_identity_module(app, None)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/content/cards/{uuid4()}/image-status",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        if previous is None:
            delattr(app.state, "identity_module_contract")
        else:
            app.state.identity_module_contract = previous

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


class TestIdentityContract:
    async def authenticate(self, access_token: str) -> AuthenticatedPrincipal:
        if access_token == "invalid":
            raise InvalidAccessTokenError()
        return AuthenticatedPrincipal(
            user_id="user-1",
            is_platform_admin=access_token == "admin",
            is_test_identity=True,
        )


class MissingCardStatus:
    async def execute(self, card_id: str) -> None:
        return None


class UnexpectedCardUseCaseCall:
    async def execute(self, command: object) -> None:
        raise AssertionError("La autorización debe ocurrir antes del caso de uso.")


class AcceptedPendingCardUseCase:
    async def execute(self, command: object) -> CreateCardResult:
        return CreateCardResult(
            snapshot=CardCreationSnapshot(
                id="card-id",
                code="PKA-FUE-001",
                name="Charmander",
                cost=0,
                power=-1,
                card_type="FUE",
                rarity="COMUN",
                ability={
                    "code": "HAB-000",
                    "name": "Sin Habilidad",
                    "trigger": None,
                    "effect": None,
                    "affected_card_type": None,
                    "parameters": {},
                },
                image_status="PENDING",
                image_url=None,
                thumbnail_url=None,
                available_to_players=False,
                status_url="/api/v1/content/cards/card-id/image-status",
            )
        )


def _valid_create_card_form() -> dict[str, str]:
    return {
        "name": "Charmander",
        "cost": "0",
        "power": "-1",
        "card_type": "FUE",
        "rarity": "COMUN",
        "ability_code": "HAB-000",
    }


@pytest.mark.asyncio
async def test_create_card_requires_bearer_before_calling_use_case() -> None:
    app.dependency_overrides[get_create_card_use_case] = lambda: UnexpectedCardUseCaseCall()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/content/cards",
                data=_valid_create_card_form(),
                files={"image": ("card.png", b"image", "image/png")},
                headers={"Idempotency-Key": "stage6-auth-check"},
            )
    finally:
        app.dependency_overrides.pop(get_create_card_use_case, None)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_card_forbids_non_admin_before_calling_use_case() -> None:
    previous = getattr(app.state, "identity_module_contract", None)
    register_identity_module(app, TestIdentityContract())
    app.dependency_overrides[get_create_card_use_case] = lambda: UnexpectedCardUseCaseCall()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/content/cards",
                data=_valid_create_card_form(),
                files={"image": ("card.png", b"image", "image/png")},
                headers={
                    "Authorization": "Bearer player",
                    "Idempotency-Key": "stage6-auth-check",
                },
            )
    finally:
        app.dependency_overrides.pop(get_create_card_use_case, None)
        if previous is None:
            delattr(app.state, "identity_module_contract")
        else:
            app.state.identity_module_contract = previous

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_card_accepts_contract_multipart_and_returns_pending_snapshot() -> None:
    previous = getattr(app.state, "identity_module_contract", None)
    register_identity_module(app, TestIdentityContract())
    app.dependency_overrides[get_create_card_use_case] = lambda: AcceptedPendingCardUseCase()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/content/cards",
                data=_valid_create_card_form(),
                files={"image": ("card.png", b"image", "image/png")},
                headers={
                    "Authorization": "Bearer admin",
                    "Idempotency-Key": "stage6-pending-check",
                },
            )
    finally:
        app.dependency_overrides.pop(get_create_card_use_case, None)
        if previous is None:
            delattr(app.state, "identity_module_contract")
        else:
            app.state.identity_module_contract = previous

    assert response.status_code == 201
    payload = response.json()
    assert payload["image_status"] == "PENDING"
    assert payload["available_to_players"] is False
    assert payload["ability"]["code"] == "HAB-000"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token", "expected_status", "error_code"),
    [("invalid", 401, "UNAUTHORIZED"), ("player", 403, "FORBIDDEN")],
)
async def test_identity_contract_maps_invalid_token_and_non_admin_separately(
    token: str, expected_status: int, error_code: str
) -> None:
    previous = getattr(app.state, "identity_module_contract", None)
    register_identity_module(app, TestIdentityContract())
    app.dependency_overrides[get_card_image_status_use_case] = lambda: MissingCardStatus()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/content/cards/{uuid4()}/image-status",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.pop(get_card_image_status_use_case, None)
        if previous is None:
            delattr(app.state, "identity_module_contract")
        else:
            app.state.identity_module_contract = previous

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == error_code


@pytest.mark.asyncio
async def test_admin_status_query_returns_rfc_error_when_card_does_not_exist() -> None:
    previous = getattr(app.state, "identity_module_contract", None)
    register_identity_module(app, TestIdentityContract())
    app.dependency_overrides[get_card_image_status_use_case] = lambda: MissingCardStatus()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/content/cards/{uuid4()}/image-status",
                headers={"Authorization": "Bearer admin"},
            )
    finally:
        app.dependency_overrides.pop(get_card_image_status_use_case, None)
        if previous is None:
            delattr(app.state, "identity_module_contract")
        else:
            app.state.identity_module_contract = previous

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CARTA_NOT_FOUND"
