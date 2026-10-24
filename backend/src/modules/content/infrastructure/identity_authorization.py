"""Content adapter for the public Identity module contract."""

from src.modules.content.application.dtos import ContentAuthenticatedPrincipalDTO
from src.modules.content.application.ports import IContentAuthorizationPort
from src.modules.identity.contracts import IIdentityModuleContract


class IdentityContentAuthorizationAdapter(IContentAuthorizationPort):
    """Translates Identity's public principal to the Content application DTO."""

    def __init__(self, identity: IIdentityModuleContract) -> None:
        self.identity = identity

    async def authenticate(self, access_token: str) -> ContentAuthenticatedPrincipalDTO:
        principal = await self.identity.authenticate(access_token)
        return ContentAuthenticatedPrincipalDTO(
            actor_id=principal.user_id,
            is_platform_admin=principal.is_platform_admin,
            is_test_identity=principal.is_test_identity,
        )
