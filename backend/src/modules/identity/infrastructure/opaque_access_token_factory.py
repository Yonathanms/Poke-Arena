"""Cryptographically random, opaque platform access credentials."""

import hashlib
import secrets

from src.modules.identity.application.dtos import IssuedAccessTokenDTO
from src.modules.identity.application.ports import IAccessTokenFactory


class OpaqueAccessTokenFactory(IAccessTokenFactory):
    def issue(self) -> IssuedAccessTokenDTO:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return IssuedAccessTokenDTO(token=token, token_hash=token_hash)
