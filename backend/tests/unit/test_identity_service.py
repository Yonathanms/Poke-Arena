import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from src.modules.identity.application.dtos import (
    GoogleIdentityDTO,
    IdentityActorDTO,
    IdentitySessionDTO,
    IssuedAccessTokenDTO,
)
from src.modules.identity.application.service import IdentityApplicationService
from src.modules.identity.contracts import InvalidAccessTokenError, InvalidGoogleCredentialError
from src.modules.identity.domain.value_objects import PlatformRole


class FakeGoogleProvider:
    async def verify_id_token(self, credential: str) -> GoogleIdentityDTO:
        return GoogleIdentityDTO(subject=credential, email="admin@example.test")


class FakeIdentityPersistence:
    def __init__(self) -> None:
        self.session: IdentitySessionDTO | None = None
        self.created_role: PlatformRole | None = None
        self.token_hash: str | None = None
        self.revoked_token_hashes: list[str] = []

    async def create_session(
        self,
        subject: str,
        email: str | None,
        role: PlatformRole,
        token_hash: str,
        expires_at: datetime,
        provider: str = "GOOGLE",
    ) -> IdentityActorDTO:
        self.created_role = role
        self.token_hash = token_hash
        self.session = IdentitySessionDTO(
            user_id="user-1",
            provider_subject=subject,
            role=role,
            expires_at=expires_at,
            is_test_identity=provider == "TEST",
        )
        return IdentityActorDTO(user_id="user-1", provider_subject=subject)

    async def get_active_session(self, token_hash: str, now: datetime) -> IdentitySessionDTO | None:
        if token_hash != self.token_hash or self.session is None or self.session.expires_at <= now:
            return None
        if token_hash in self.revoked_token_hashes:
            return None
        return self.session

    async def revoke_session(self, token_hash: str, revoked_at: datetime) -> None:
        self.revoked_token_hashes.append(token_hash)


class FakeTokenFactory:
    def issue(self) -> IssuedAccessTokenDTO:
        token = "platform-token"
        return IssuedAccessTokenDTO(
            token=token,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        )


@pytest.mark.asyncio
async def test_login_assigns_admin_only_from_server_subject_configuration() -> None:
    persistence = FakeIdentityPersistence()
    service = IdentityApplicationService(
        FakeGoogleProvider(), persistence, FakeTokenFactory(), frozenset({"google-sub-1"}), 900
    )

    result = await service.login_with_google("google-sub-1")

    assert result.role is PlatformRole.PLATFORM_ADMIN
    assert persistence.created_role is PlatformRole.PLATFORM_ADMIN
    principal = await service.authenticate(result.access_token)
    assert principal.user_id == "user-1"
    assert principal.is_platform_admin is True


@pytest.mark.asyncio
async def test_login_defaults_to_player_and_access_token_is_required_in_persistence() -> None:
    persistence = FakeIdentityPersistence()
    service = IdentityApplicationService(
        FakeGoogleProvider(), persistence, FakeTokenFactory(), frozenset(), 900
    )

    result = await service.login_with_google("google-sub-player")

    assert result.role is PlatformRole.PLAYER
    principal = await service.authenticate(result.access_token)
    assert principal.is_platform_admin is False


@pytest.mark.asyncio
async def test_expired_or_unknown_platform_token_is_rejected() -> None:
    persistence = FakeIdentityPersistence()
    service = IdentityApplicationService(
        FakeGoogleProvider(), persistence, FakeTokenFactory(), frozenset(), 900
    )

    with pytest.raises(InvalidAccessTokenError):
        await service.authenticate("unknown-token")

    persistence.session = IdentitySessionDTO(
        user_id="user-1",
        provider_subject="google-sub-1",
        role=PlatformRole.PLAYER,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(InvalidAccessTokenError):
        await service.authenticate("platform-token")


@pytest.mark.asyncio
async def test_logout_revokes_the_platform_access_token() -> None:
    persistence = FakeIdentityPersistence()
    service = IdentityApplicationService(
        FakeGoogleProvider(), persistence, FakeTokenFactory(), frozenset(), 900
    )
    session = await service.login_with_google("google-sub-1")

    await service.logout(session.access_token)

    with pytest.raises(InvalidAccessTokenError):
        await service.authenticate(session.access_token)


@pytest.mark.asyncio
async def test_local_test_identity_is_admin_only_when_explicitly_enabled() -> None:
    persistence = FakeIdentityPersistence()
    service = IdentityApplicationService(
        FakeGoogleProvider(),
        persistence,
        FakeTokenFactory(),
        frozenset(),
        900,
        allow_test_identity=True,
    )

    result = await service.login_with_test_identity("local-admin")

    assert result.provider == "TEST"
    assert result.role is PlatformRole.PLATFORM_ADMIN
    principal = await service.authenticate(result.access_token)
    assert principal.is_platform_admin is True
    assert principal.is_test_identity is True
    assert persistence.session is not None
    assert persistence.session.provider_subject == "local:local-admin"

    disabled_service = IdentityApplicationService(
        FakeGoogleProvider(), persistence, FakeTokenFactory(), frozenset(), 900
    )
    with pytest.raises(InvalidGoogleCredentialError):
        await disabled_service.login_with_test_identity()
