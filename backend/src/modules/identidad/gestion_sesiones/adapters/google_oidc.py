"""Verificación criptográfica de Google ID tokens con claves públicas de Google."""

import logging
from asyncio import to_thread
from functools import lru_cache

import jwt
from jwt import (
    PyJWK,
    PyJWKClient,
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWTError,
)

from ..domain.sesion_model import IdentidadInvalida, IdentidadNoDisponible

logger = logging.getLogger(__name__)

_GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
_EMISORES = ("https://accounts.google.com", "accounts.google.com")
_LEEWAY_SECONDS = 30  # Tolerancia ante desviación de reloj NTP entre Google y el servidor


class IdentidadGoogle(str):
    """Representación string de subject que conserva metadatos verificados."""

    subject: str
    email: str | None
    name: str | None
    picture: str | None
    email_verified: bool

    def __new__(
        cls,
        subject: str,
        email: str | None = None,
        name: str | None = None,
        picture: str | None = None,
        *,
        email_verified: bool = False,
    ) -> "IdentidadGoogle":
        obj = super().__new__(cls, subject)
        obj.subject = subject
        obj.email = email
        obj.name = name
        obj.picture = picture
        obj.email_verified = email_verified
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
            logger.warning("oidc_google_cabecera_invalida")
            raise IdentidadInvalida()

        client = _claves()
        clave: PyJWK | None
        if hasattr(client, "get_signing_key"):
            try:
                clave = client.get_signing_key(kid)
            except PyJWKClientConnectionError:
                raise IdentidadNoDisponible() from None
            except PyJWKClientError:
                logger.warning("oidc_google_clave_no_encontrada")
                raise IdentidadInvalida() from None
        else:
            clave = next(
                (k for k in client.get_signing_keys() if getattr(k, "key_id", None) == kid),
                None,
            )
            if clave is None:
                logger.warning("oidc_google_clave_no_encontrada")
                raise IdentidadInvalida()

        signing_key = clave.key if hasattr(clave, "key") else clave

        claims = jwt.decode(
            credencial,
            signing_key,
            algorithms=["RS256"],
            issuer=_EMISORES,
            audience=client_id,
            options={"require": ["exp", "iat", "iss", "aud", "sub"], "strict_aud": True},
            leeway=_LEEWAY_SECONDS,
        )
    except PyJWKClientConnectionError:
        raise IdentidadNoDisponible() from None
    except PyJWTError:
        logger.warning("oidc_google_jwt_invalido")
        raise IdentidadInvalida() from None
    except (ValueError, TypeError, OverflowError):
        logger.warning("oidc_google_estructura_invalida")
        raise IdentidadInvalida() from None

    subject = claims.get("sub")
    if (
        not isinstance(subject, str)
        or not 1 <= len(subject) <= 255
        or not subject.isascii()
        or not subject.isprintable()
        or any(caracter.isspace() for caracter in subject)
    ):
        logger.warning("Claim sub inválido en Google ID token")
        raise IdentidadInvalida()

    # Validación de Authorized Party (azp) según OpenID Connect Core 1.0 §3.1.3.7
    azp = claims.get("azp")
    if azp is not None and azp != client_id:
        logger.warning("oidc_google_azp_invalido")
        raise IdentidadInvalida()

    exp = claims.get("exp")
    iat = claims.get("iat")
    if type(exp) is not int or type(iat) is not int:
        logger.warning("Claims temporales exp/iat no enteros en Google ID token")
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
        email_verified=email is not None and claims.get("email_verified") is True,
    )


async def verificar_google(credencial: str, client_id: str | None) -> IdentidadGoogle:
    """Verifica un ID token fuera del loop y rechaza configuración incompleta."""
    if not client_id or not client_id.strip():
        raise IdentidadNoDisponible()
    return await to_thread(_verificar, credencial, client_id)
