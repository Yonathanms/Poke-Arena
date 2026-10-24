from datetime import UTC, datetime, timedelta

import httpx
import pytest

from src.modules.identity.contracts import (
    IdentityServiceUnavailableError,
    InvalidGoogleCredentialError,
)
from src.modules.identity.infrastructure.google_identity_provider import GoogleIdentityProvider


def _token_info(audience: str = "pokearena-client") -> dict[str, str]:
    return {
        "aud": audience,
        "exp": str(int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())),
        "iss": "https://accounts.google.com",
        "sub": "google-subject-1",
        "email": "player@example.test",
    }


@pytest.mark.asyncio
async def test_google_token_verification_checks_audience_and_expiry() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["id_token"] == "google-id-token"
        return httpx.Response(200, json=_token_info())

    provider = GoogleIdentityProvider(
        "pokearena-client", transport=httpx.MockTransport(handler)
    )

    identity = await provider.verify_id_token("google-id-token")

    assert identity.subject == "google-subject-1"
    assert identity.email == "player@example.test"


@pytest.mark.asyncio
async def test_google_token_with_wrong_audience_is_rejected() -> None:
    provider = GoogleIdentityProvider(
        "pokearena-client",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=_token_info("different-client"))
        ),
    )

    with pytest.raises(InvalidGoogleCredentialError):
        await provider.verify_id_token("google-id-token")


@pytest.mark.asyncio
async def test_google_rejection_and_outage_are_distinguished() -> None:
    rejected = GoogleIdentityProvider(
        "pokearena-client",
        transport=httpx.MockTransport(lambda request: httpx.Response(400)),
    )
    with pytest.raises(InvalidGoogleCredentialError):
        await rejected.verify_id_token("invalid-token")

    unavailable = GoogleIdentityProvider(
        "pokearena-client",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(503)
        ),
    )
    with pytest.raises(IdentityServiceUnavailableError):
        await unavailable.verify_id_token("google-id-token")


@pytest.mark.asyncio
async def test_google_login_requires_configured_client_id() -> None:
    provider = GoogleIdentityProvider(None)

    with pytest.raises(IdentityServiceUnavailableError):
        await provider.verify_id_token("google-id-token")
