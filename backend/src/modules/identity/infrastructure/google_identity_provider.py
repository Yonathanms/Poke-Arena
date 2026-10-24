"""Google ID token verification adapter."""

from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, ValidationError

from src.modules.identity.application.dtos import GoogleIdentityDTO
from src.modules.identity.application.ports import IGoogleIdentityProvider
from src.modules.identity.contracts import (
    IdentityServiceUnavailableError,
    InvalidGoogleCredentialError,
)


class GoogleTokenInfo(BaseModel):
    aud: str
    exp: str
    iss: str
    sub: str
    email: str | None = None


class GoogleIdentityProvider(IGoogleIdentityProvider):
    TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"

    def __init__(
        self,
        client_id: str | None,
        timeout_seconds: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client_id = client_id
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def verify_id_token(self, credential: str) -> GoogleIdentityDTO:
        if not self.client_id:
            raise IdentityServiceUnavailableError()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.get(self.TOKEN_INFO_URL, params={"id_token": credential})
        except httpx.HTTPError as exc:
            raise IdentityServiceUnavailableError() from exc

        if response.status_code in {400, 401}:
            raise InvalidGoogleCredentialError()
        if response.status_code >= 500:
            raise IdentityServiceUnavailableError()
        if response.status_code != 200:
            raise IdentityServiceUnavailableError()
        try:
            token_info = GoogleTokenInfo.model_validate(response.json())
            expiry = int(token_info.exp)
        except (ValidationError, TypeError, ValueError) as exc:
            raise InvalidGoogleCredentialError() from exc

        if (
            token_info.aud != self.client_id
            or token_info.iss not in {"accounts.google.com", "https://accounts.google.com"}
            or expiry <= int(datetime.now(UTC).timestamp())
            or not token_info.sub
        ):
            raise InvalidGoogleCredentialError()

        return GoogleIdentityDTO(subject=token_info.sub, email=token_info.email)
