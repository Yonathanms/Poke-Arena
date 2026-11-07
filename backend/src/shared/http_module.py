"""Composición de los componentes HTTP compartidos con rutas oficiales con guiones."""

from importlib import import_module
from typing import cast

from fastapi import HTTPException

_errores = import_module("src.shared.errores-rfc7807.respuestas")
_bearer = import_module("src.shared.seguridad-roles.bearer")

registrar_errores = _errores.registrar_errores
respuestas_documentadas = _errores.respuestas_documentadas
credencial_invalida = _bearer.credencial_invalida
token_plataforma = _bearer.token_plataforma


def problema(
    status: int, codigo: str, mensaje: str, headers: dict[str, str] | None = None
) -> HTTPException:
    """Publica el constructor tipado del formato compartido de errores."""
    return cast(HTTPException, _errores.problema(status, codigo, mensaje, headers))
