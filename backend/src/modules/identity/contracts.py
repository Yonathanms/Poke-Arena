"""Public Identity contract consumed by other business modules."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Claims verified by Identity after validating a Poké-Arena access token."""

    user_id: str
    is_platform_admin: bool
    is_test_identity: bool = False


class InvalidAccessTokenError(Exception):
    """The access token is missing, malformed, expired, or revoked."""


class IdentityServiceUnavailableError(Exception):
    """Identity cannot currently validate credentials."""


class InvalidGoogleCredentialError(Exception):
    """The Google credential is invalid or was issued for another application."""


class IIdentityModuleContract(Protocol):
    """Public API; token format and cryptography remain private to Identity."""

    async def authenticate(self, access_token: str) -> AuthenticatedPrincipal: ...
