"""Identity application ports."""

from datetime import datetime
from typing import Protocol

from src.modules.identity.application.dtos import (
    GoogleIdentityDTO,
    IdentityActorDTO,
    IdentitySessionDTO,
    IssuedAccessTokenDTO,
)
from src.modules.identity.domain.value_objects import PlatformRole


class IGoogleIdentityProvider(Protocol):
    async def verify_id_token(self, credential: str) -> GoogleIdentityDTO: ...


class IIdentityPersistence(Protocol):
    async def create_session(
        self,
        subject: str,
        email: str | None,
        role: PlatformRole,
        token_hash: str,
        expires_at: datetime,
        provider: str = "GOOGLE",
    ) -> IdentityActorDTO: ...

    async def get_active_session(
        self, token_hash: str, now: datetime
    ) -> IdentitySessionDTO | None: ...

    async def revoke_session(self, token_hash: str, revoked_at: datetime) -> None: ...


class IAccessTokenFactory(Protocol):
    def issue(self) -> IssuedAccessTokenDTO: ...
