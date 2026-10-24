"""HTTP DTOs for the Identity module."""

from pydantic import BaseModel, ConfigDict, Field

from src.modules.identity.domain.value_objects import PlatformRole


class GoogleLoginRequest(BaseModel):
    google_id_token: str = Field(min_length=1, max_length=8192)


class LocalTestLoginRequest(BaseModel):
    user_id: str = Field(
        default="local-admin", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"
    )

    model_config = ConfigDict(extra="forbid")


class PlatformSessionResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    role: PlatformRole
