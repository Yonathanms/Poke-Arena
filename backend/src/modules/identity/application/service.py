"""Application service implementing Identity login and the public module contract."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.modules.identity.application.ports import (
    IAccessTokenFactory,
    IGoogleIdentityProvider,
    IIdentityPersistence,
)
from src.modules.identity.contracts import (
    AuthenticatedPrincipal,
    InvalidAccessTokenError,
    InvalidGoogleCredentialError,
)
from src.modules.identity.domain.value_objects import PlatformRole


@dataclass(frozen=True)
class GoogleLoginResult:
    user_id: str
    role: PlatformRole
    access_token: str
    expires_in: int
    provider: str = "GOOGLE"


class IdentityApplicationService:
    """Issues opaque platform credentials and validates them against SQL sessions."""

    def __init__(
        self,
        google_provider: IGoogleIdentityProvider,
        persistence: IIdentityPersistence,
        token_factory: IAccessTokenFactory,
        platform_admin_subjects: frozenset[str],
        access_token_ttl_seconds: int,
        allow_test_identity: bool = False,
    ) -> None:
        if access_token_ttl_seconds < 60:
            raise ValueError("La duración del token debe ser de al menos 60 segundos.")
        self.google_provider = google_provider
        self.persistence = persistence
        self.token_factory = token_factory
        self.platform_admin_subjects = platform_admin_subjects
        self.access_token_ttl_seconds = access_token_ttl_seconds
        self.allow_test_identity = allow_test_identity

    async def login_with_google(self, credential: str) -> GoogleLoginResult:
        if not credential.strip():
            raise InvalidGoogleCredentialError()
        identity = await self.google_provider.verify_id_token(credential)
        role = (
            PlatformRole.PLATFORM_ADMIN
            if identity.subject in self.platform_admin_subjects
            else PlatformRole.PLAYER
        )
        issued = self.token_factory.issue()
        expires_at = datetime.now(UTC) + timedelta(seconds=self.access_token_ttl_seconds)
        actor = await self.persistence.create_session(
            subject=identity.subject,
            email=identity.email,
            role=role,
            token_hash=issued.token_hash,
            expires_at=expires_at,
        )
        return GoogleLoginResult(
            user_id=actor.user_id,
            role=role,
            access_token=issued.token,
            expires_in=self.access_token_ttl_seconds,
        )

    async def login_with_test_identity(self, user_id: str = "local-admin") -> GoogleLoginResult:
        """Issue a local administrator only when the application explicitly enables it."""
        if not self.allow_test_identity:
            raise InvalidGoogleCredentialError()
        subject = user_id.strip()
        if (
            not subject
            or len(subject) > 80
            or not subject.replace("-", "").replace("_", "").isalnum()
        ):
            raise InvalidGoogleCredentialError()
        role = PlatformRole.PLATFORM_ADMIN
        issued = self.token_factory.issue()
        expires_at = datetime.now(UTC) + timedelta(seconds=self.access_token_ttl_seconds)
        actor = await self.persistence.create_session(
            subject=f"local:{subject}",
            email=None,
            role=role,
            token_hash=issued.token_hash,
            expires_at=expires_at,
            provider="TEST",
        )
        return GoogleLoginResult(
            user_id=actor.user_id,
            role=role,
            access_token=issued.token,
            expires_in=self.access_token_ttl_seconds,
            provider="TEST",
        )

    async def authenticate(self, access_token: str) -> AuthenticatedPrincipal:
        if not access_token:
            raise InvalidAccessTokenError()
        token_hash = hashlib.sha256(access_token.encode("utf-8")).hexdigest()
        session = await self.persistence.get_active_session(token_hash, datetime.now(UTC))
        if session is None:
            raise InvalidAccessTokenError()
        # Re-evaluate admin membership from server configuration on each request.
        return AuthenticatedPrincipal(
            user_id=session.user_id,
            is_platform_admin=(
                session.is_test_identity or session.provider_subject in self.platform_admin_subjects
            ),
            is_test_identity=session.is_test_identity,
        )

    async def logout(self, access_token: str) -> None:
        if not access_token:
            raise InvalidAccessTokenError()
        token_hash = hashlib.sha256(access_token.encode("utf-8")).hexdigest()
        await self.persistence.revoke_session(token_hash, datetime.now(UTC))
