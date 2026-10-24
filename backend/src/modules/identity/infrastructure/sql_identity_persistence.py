"""SQL adapter for Identity accounts and revocable access sessions."""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.identity.application.dtos import IdentityActorDTO, IdentitySessionDTO
from src.modules.identity.application.ports import IIdentityPersistence
from src.modules.identity.contracts import IdentityServiceUnavailableError
from src.modules.identity.domain.value_objects import PlatformRole
from src.modules.identity.infrastructure.models import IdentitySessionModel, IdentityUserModel


class SqlIdentityPersistence(IIdentityPersistence):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_session(
        self,
        subject: str,
        email: str | None,
        role: PlatformRole,
        token_hash: str,
        expires_at: datetime,
        provider: str = "GOOGLE",
    ) -> IdentityActorDTO:
        try:
            async with self.session_factory() as session, session.begin():
                statement = (
                    insert(IdentityUserModel)
                    .values(
                        id=str(uuid.uuid4()),
                        provider=provider,
                        provider_subject=subject,
                        email=email,
                        role=role.value,
                    )
                    .on_conflict_do_update(
                        constraint="uq_identity_provider_subject",
                        set_={"email": email, "role": role.value, "updated_at": func.now()},
                    )
                    .returning(IdentityUserModel.id)
                )
                user_id = (await session.execute(statement)).scalar_one()
                session.add(
                    IdentitySessionModel(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        token_hash=token_hash,
                        expires_at=expires_at,
                    )
                )
                await session.flush()
            return IdentityActorDTO(user_id=user_id, provider_subject=subject)
        except SQLAlchemyError as exc:
            raise IdentityServiceUnavailableError() from exc

    async def get_active_session(self, token_hash: str, now: datetime) -> IdentitySessionDTO | None:
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(IdentityUserModel, IdentitySessionModel)
                    .join(
                        IdentitySessionModel,
                        IdentitySessionModel.user_id == IdentityUserModel.id,
                    )
                    .where(
                        IdentitySessionModel.token_hash == token_hash,
                        IdentitySessionModel.revoked_at.is_(None),
                        IdentitySessionModel.expires_at > now,
                    )
                )
                row = result.one_or_none()
                if row is None:
                    return None
                user, identity_session = row
                return IdentitySessionDTO(
                    user_id=user.id,
                    provider_subject=user.provider_subject,
                    role=PlatformRole(user.role),
                    expires_at=identity_session.expires_at,
                    is_test_identity=user.provider == "TEST",
                )
        except SQLAlchemyError as exc:
            raise IdentityServiceUnavailableError() from exc

    async def revoke_session(self, token_hash: str, revoked_at: datetime) -> None:
        try:
            async with self.session_factory() as session, session.begin():
                await session.execute(
                    update(IdentitySessionModel)
                    .where(
                        IdentitySessionModel.token_hash == token_hash,
                        IdentitySessionModel.revoked_at.is_(None),
                    )
                    .values(revoked_at=revoked_at)
                )
        except SQLAlchemyError as exc:
            raise IdentityServiceUnavailableError() from exc
