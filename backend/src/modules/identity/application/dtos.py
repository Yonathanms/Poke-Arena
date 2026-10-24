"""Identity application DTOs; no HTTP or persistence models cross the boundary."""

from dataclasses import dataclass
from datetime import datetime

from src.modules.identity.domain.value_objects import PlatformRole


@dataclass(frozen=True)
class GoogleIdentityDTO:
    subject: str
    email: str | None


@dataclass(frozen=True)
class IdentityActorDTO:
    user_id: str
    provider_subject: str


@dataclass(frozen=True)
class IssuedAccessTokenDTO:
    token: str
    token_hash: str


@dataclass(frozen=True)
class IdentitySessionDTO:
    user_id: str
    provider_subject: str
    role: PlatformRole
    expires_at: datetime
    is_test_identity: bool = False
