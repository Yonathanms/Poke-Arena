"""Verificación criptográfica de Google ID tokens con claves públicas de Google."""

from asyncio import to_thread
from functools import lru_cache

import jwt
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWTError

from ..domain.sesion_model import IdentidadInvalida, IdentidadNoDisponible

_GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
_EMISORES = ("https://accounts.google.com", "accounts.google.com")


class IdentidadGoogle(str):
    """Representación string de subject que conserva metadatos verificados."""

    subject: str
    email: str | None
    name: str | None
    picture: str | None

    def __new__(
        cls,
        subject: str,
        email: str | None = None,
        name: str | None = None,
        picture: str | None = None,
    ) -> "IdentidadGoogle":
        obj = super().__new__(cls, subject)
        obj.subject = subject
        obj.email = email
        obj.name = name
        obj.picture = picture
        return obj


@lru_cache(maxsize=1)
def _claves() -> PyJWKClient:
    return PyJWKClient(_GOOGLE_JWKS, timeout=5, lifespan=300)


def _verificar(credencial: str, client_id: str) -> IdentidadGoogle:
    """Verifica firma RS256 y claims antes de devolver el identificador estable."""
    try:
        header = jwt.get_unverified_header(credencial)
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not 0 < len(kid) <= 128:
            raise IdentidadInvalida()
        # Un kid ajeno no puede forzar una consulta HTTPS por solicitud.
        clave = next((k for k in _claves().get_signing_keys() if k.key_id == kid), None)
        if clave is None:
            raise IdentidadInvalida()
        claims = jwt.decode(
            credencial,
            clave,
            algorithms=["RS256"],
            issuer=_EMISORES,
            audience=client_id,
            options={"require": ["exp", "iat", "iss", "aud", "sub"], "strict_aud": True},
        )
    except PyJWKClientConnectionError:
        raise IdentidadNoDisponible() from None
    except (PyJWTError, ValueError, TypeError, OverflowError):
        raise IdentidadInvalida() from None
    subject = claims["sub"]
    if (
        not isinstance(subject, str)
        or not 1 <= len(subject) <= 255
        or not subject.isascii()
        or not subject.isprintable()
        or any(caracter.isspace() for caracter in subject)
        or claims.get("azp", client_id) != client_id
        or type(claims["exp"]) is not int
        or type(claims["iat"]) is not int
    ):
        raise IdentidadInvalida()

    raw_email = claims.get("email")
    email = (
        raw_email.strip().lower()
        if isinstance(raw_email, str) and raw_email.strip()
        else None
    )
    name = claims.get("name") if isinstance(claims.get("name"), str) else None
    picture = claims.get("picture") if isinstance(claims.get("picture"), str) else None

    return IdentidadGoogle(
        subject=subject,
        email=email,
        name=name,
        picture=picture,
    )


async def verificar_google(credencial: str, client_id: str | None) -> IdentidadGoogle:
    """Verifica un ID token fuera del loop y rechaza configuración incompleta."""
    if not client_id or not client_id.strip():
        raise IdentidadNoDisponible()
    return await to_thread(_verificar, credencial, client_id)
