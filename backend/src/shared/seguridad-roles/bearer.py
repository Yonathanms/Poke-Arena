"""Extracción del token opaco de plataforma para dependencias HTTP."""

from re import fullmatch

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False, scheme_name="PlatformBearerAuth", bearerFormat="opaque")


def credencial_invalida() -> HTTPException:
    """Solicita una credencial Bearer sin revelar detalles de la autenticación."""
    return HTTPException(
        401,
        {"code": "credencial_invalida", "detail": "Se requiere una sesión válida de Poké-Arena."},
        {"WWW-Authenticate": "Bearer"},
    )


def token_plataforma(
    request: Request,
    credencial: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Acepta el formato histórico token_urlsafe(32) antes de consultar identidad."""
    if (
        credencial is None
        or len(request.headers.getlist("authorization")) != 1
        or not fullmatch(r"[A-Za-z0-9_-]{43}", credencial.credentials)
    ):
        raise credencial_invalida()
    return credencial.credentials
