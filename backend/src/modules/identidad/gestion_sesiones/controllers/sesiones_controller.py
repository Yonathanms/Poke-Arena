"""Intercambio OIDC y dependencias de autenticación de plataforma."""

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from starlette.requests import ClientDisconnect

from src.shared.config import get_settings
from src.shared.http_module import (
    credencial_invalida,
    problema,
    respuestas_documentadas,
    token_plataforma,
)
from src.shared.validacion.cuerpo import CuerpoExcesivo, flujo_acotado

from ..domain.sesion_model import (
    IdentidadInvalida,
    IdentidadLimitada,
    IdentidadNoDisponible,
    Rol,
    SesionEmitida,
)
from ..services.sesiones_service import Sesiones


class CredencialGoogle(BaseModel):
    """ID token para el client ID registrado, excluido de la representación en claro."""

    model_config = ConfigDict(extra="forbid")
    google_id_token: SecretStr = Field(min_length=1, max_length=8192)


class CredencialLocal(BaseModel):
    """Credencial del administrador local aprovisionado fuera de HTTP."""

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=63)
    password: SecretStr = Field(min_length=1, max_length=256)


class RespuestaSesion(BaseModel):
    """Token opaco y metadatos de sesión del contrato histórico."""

    access_token: str = Field(repr=False)
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    user_id: str
    role: Rol


def crear_router(
    servicio: Callable[[], Sesiones],
    verificar: Callable[[str, str | None], Awaitable[str]],
) -> tuple[APIRouter, Callable[..., Awaitable[str]]]:
    """Construye la ruta de intercambio y la dependencia pública de administrador."""
    router = APIRouter(prefix="/identity", tags=["Identity"])

    async def administrador(token: str = Depends(token_plataforma)) -> str:
        """Devuelve el ID SQL autorizado con una credencial opaca vigente."""
        try:
            principal = await servicio().autenticar(token)
        except IdentidadInvalida:
            raise credencial_invalida() from None
        except IdentidadNoDisponible:
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None
        if principal.rol != "PLATFORM_ADMIN":
            raise problema(403, "permiso_denegado", "Se requiere el rol PLATFORM_ADMIN.")
        return principal.id

    @router.post(
        "/local/session",
        status_code=201,
        operation_id="createLocalSession",
        openapi_extra=_esquema_json(CredencialLocal),
        responses=respuestas_documentadas(
            {
                401: "Credenciales inválidas",
                404: "Login local deshabilitado",
                413: "Cuerpo demasiado grande",
                415: "Se requiere application/json",
                422: "Solicitud inválida",
                429: "Límite temporal de intentos",
                503: "Identidad no disponible",
            }
        ),
    )
    async def crear_local(request: Request, response: Response) -> RespuestaSesion:
        """Verifica un secreto aprovisionado y emite la sesión compartida."""
        if not get_settings().IDENTITY_LOCAL_ENABLED:
            raise problema(404, "http_error", "La ruta no está disponible.")
        loopback = request.client is not None and request.client.host in {"127.0.0.1", "::1"}
        if request.url.scheme != "https" and not loopback:
            raise problema(404, "http_error", "La ruta no está disponible.")
        credencial = await _leer_credencial(request, CredencialLocal)
        try:
            sesion = await servicio().emitir_local(
                credencial.username, credencial.password.get_secret_value()
            )
        except IdentidadInvalida:
            raise problema(401, "credencial_invalida", "Credenciales inválidas.") from None
        except IdentidadLimitada as error:
            raise problema(
                429,
                "intentos_limitados",
                "Reintenta después del período de espera.",
                {"Retry-After": str(error.segundos)},
            ) from None
        except IdentidadNoDisponible:
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None
        return _respuesta_sesion(sesion, response)

    @router.delete(
        "/session",
        status_code=204,
        operation_id="revokePlatformSession",
        responses=respuestas_documentadas(
            {401: "Bearer requerido", 503: "Identidad no disponible"}
        ),
    )
    async def revocar_sesion(token: str = Depends(token_plataforma)) -> Response:
        """Revoca el Bearer presentado sin afectar otras sesiones."""
        try:
            await servicio().revocar(token)
        except IdentidadNoDisponible:
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        return Response(status_code=204)

    @router.post(
        "/google/session",
        status_code=201,
        operation_id="createGoogleSession",
        openapi_extra=_esquema_json(CredencialGoogle),
        responses=respuestas_documentadas(
            {
                401: "ID token inválido",
                413: "Cuerpo demasiado grande",
                415: "Se requiere application/json",
                422: "Solicitud inválida",
                503: "Identidad no disponible",
                500: "Error interno",
            }
        ),
    )
    async def crear_sesion(request: Request, response: Response) -> RespuestaSesion:
        """Intercambia un ID token verificado por una sesión opaca de Poké-Arena."""
        credencial = await _leer_credencial(request, CredencialGoogle)
        try:
            subject = await verificar(
                credencial.google_id_token.get_secret_value(), get_settings().GOOGLE_OAUTH_CLIENT_ID
            )
            sesion = await servicio().emitir(subject)
        except IdentidadInvalida:
            raise problema(
                401,
                "google_credencial_invalida",
                "El ID token de Google no es válido.",
            ) from None
        except IdentidadNoDisponible:
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None
        return _respuesta_sesion(sesion, response)

    return router, administrador


def _respuesta_sesion(sesion: SesionEmitida, response: Response) -> RespuestaSesion:
    response.headers["Cache-Control"] = "no-store"
    return RespuestaSesion(
        access_token=sesion.token,
        expires_in=sesion.expira_en,
        user_id=sesion.principal.id,
        role=sesion.principal.rol,
    )


def _esquema_json(modelo: type[BaseModel]) -> dict[str, object]:
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": modelo.model_json_schema()}},
        }
    }


async def _leer_credencial[Credencial: BaseModel](
    request: Request, modelo: type[Credencial]
) -> Credencial:
    """Valida JSON de tamaño acotado sin registrar su contenido."""
    tipo = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if tipo != "application/json":
        raise problema(415, "json_requerido", "Usa application/json.")
    try:
        cuerpo = bytearray()
        async for fragmento in flujo_acotado(request, 16_384):
            cuerpo.extend(fragmento)
        return modelo.model_validate_json(cuerpo)
    except CuerpoExcesivo:
        raise problema(413, "cuerpo_demasiado_grande", "El cuerpo supera el límite.") from None
    except (ValidationError, ClientDisconnect):
        raise problema(422, "solicitud_invalida", "Verifica el cuerpo de la solicitud.") from None
