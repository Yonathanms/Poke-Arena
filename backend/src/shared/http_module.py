"""Composición de los componentes HTTP compartidos."""

from typing import cast

from fastapi import HTTPException

from src.shared.errores_rfc7807.respuestas import (
    problema as _problema_fn,
    registrar_errores,
    respuestas_documentadas,
)
from src.shared.seguridad_roles.bearer import credencial_invalida, token_plataforma


def problema(
    status: int, codigo: str, mensaje: str, headers: dict[str, str] | None = None
) -> HTTPException:
    """Publica el constructor tipado del formato compartido de errores."""
    return cast(HTTPException, _problema_fn(status, codigo, mensaje, headers))
