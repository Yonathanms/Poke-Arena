"""Identity domain value objects."""

from enum import StrEnum


class PlatformRole(StrEnum):
    PLAYER = "PLAYER"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
