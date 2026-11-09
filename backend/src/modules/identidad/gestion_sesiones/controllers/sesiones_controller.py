"""Intercambio OIDC y dependencias de autenticación de plataforma."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
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
    IdentidadEnConflicto,
    IdentidadInvalida,
    IdentidadLimitada,
    IdentidadNoDisponible,
    Principal,
    Rol,
    SesionEmitida,
)
from ..services.sesiones_service import Sesiones

logger = logging.getLogger(__name__)


def _conflicto_identidad(status: Literal[403, 409]) -> HTTPException:
    return problema(status, "identidad_tipo_en_conflicto", "Autorización de cuenta incompatible.")


class CredencialGoogle(BaseModel):
    """ID token para el client ID registrado, excluido de la representación en claro."""

    model_config = ConfigDict(extra="forbid")
    google_id_token: SecretStr | None = Field(default=None, min_length=1, max_length=8192)
    id_token: SecretStr | None = Field(default=None, min_length=1, max_length=8192)

    @model_validator(mode="after")
    def validar_token_presente(self) -> "CredencialGoogle":
        if not self.google_id_token and not self.id_token:
            raise ValueError("Se requiere 'id_token' o 'google_id_token'")
        return self

    @property
    def token_value(self) -> str:
        token = self.id_token or self.google_id_token
        assert token is not None
        return token.get_secret_value()


class CredencialLocal(BaseModel):
    """Credencial del administrador local aprovisionado fuera de HTTP."""

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=63)
    password: SecretStr = Field(min_length=1, max_length=256)


class RespuestaSesion(BaseModel):
    """Token de sesión y metadatos del usuario autenticado."""

    access_token: str = Field(repr=False)
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    user_id: str
    role: Rol
    email: str | None = None
    is_new_user: bool = False


class RespuestaPerfil(BaseModel):
    """Información de la cuenta y perfil del jugador en PostgreSQL."""

    user_id: str
    email: str | None = None
    role: Rol
    elo: int = 0
    cubes: int = 0
    has_received_initial_collection: bool = False
    created_at: str | None = None


def crear_dependencias(
    servicio: Callable[[], Sesiones],
) -> tuple[Callable[..., Awaitable[str]], Callable[..., Awaitable[Principal]]]:
    """Compone las dependencias públicas de autenticación de Identidad."""

    async def administrador(token: str = Depends(token_plataforma)) -> str:
        """Devuelve el ID SQL autorizado con una credencial opaca vigente."""
        try:
            principal = await servicio().autenticar(token)
        except IdentidadInvalida:
            raise credencial_invalida() from None
        except IdentidadEnConflicto:
            raise _conflicto_identidad(403) from None
        except IdentidadNoDisponible:
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None
        if principal.rol != "PLATFORM_ADMIN":
            raise problema(403, "permiso_denegado", "Se requiere el rol PLATFORM_ADMIN.")
        return principal.id

    async def jugador(token: str = Depends(token_plataforma)) -> Principal:
        """Valida que la sesión esté activa y pertenezca a un jugador o administrador."""
        try:
            return await servicio().autenticar(token)
        except IdentidadInvalida:
            raise credencial_invalida() from None
        except IdentidadEnConflicto:
            raise _conflicto_identidad(403) from None
        except IdentidadNoDisponible:
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None

    return administrador, jugador


def crear_router(
    servicio: Callable[[], Sesiones],
    verificar: Callable[[str, str | None], Awaitable[Any]],
    autenticar: Callable[..., Awaitable[Principal]],
    provisionar: Callable[[str], Awaitable[None]],
) -> APIRouter:
    """Compone las rutas de sesión con el callback de provisión de la aplicación."""
    router = APIRouter(prefix="/identity", tags=["Identity"])

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

    async def _intercambiar_google(request: Request, response: Response) -> RespuestaSesion:
        credencial = await _leer_credencial(request, CredencialGoogle)
        try:
            identidad = await verificar(
                credencial.token_value, get_settings().GOOGLE_OAUTH_CLIENT_ID
            )
            email = getattr(identidad, "email", None)
            sesion = await servicio().emitir(
                str(identidad),
                email=email,
                email_verified=getattr(identidad, "email_verified", False) is True,
            )
        except IdentidadEnConflicto:
            logger.warning("Ingreso Google rechazado por conflicto de tipo de cuenta")
            raise _conflicto_identidad(409) from None
        except IdentidadInvalida:
            logger.warning("Fallo al autenticar credencial Google: token inválido")
            raise problema(
                401,
                "google_credencial_invalida",
                "El ID token de Google no es válido.",
            ) from None
        except IdentidadNoDisponible:
            logger.error("Servicio de verificación de Google no disponible")
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        except Exception:
            logger.error("oidc_google_error_interno")
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None
        if sesion.principal.rol == "PLAYER":
            await provisionar(sesion.token)
        return _respuesta_sesion(sesion, response)

    @router.post(
        "/google/session",
        status_code=201,
        operation_id="createGoogleSession",
        openapi_extra=_esquema_json(CredencialGoogle),
        responses=respuestas_documentadas(
            {
                401: "ID token inválido",
                403: "Jugador no elegible",
                409: "Tipo de cuenta incompatible o estado de provisión inconsistente",
                413: "Cuerpo demasiado grande",
                415: "Se requiere application/json",
                422: "Solicitud inválida",
                503: "Identidad o provisión no disponible",
                500: "Error interno",
            }
        ),
    )
    async def crear_sesion(request: Request, response: Response) -> RespuestaSesion:
        """Intercambia un ID token verificado por una sesión opaca de Poké-Arena (201 Created)."""
        return await _intercambiar_google(request, response)

    @router.post(
        "/login/google",
        status_code=200,
        operation_id="loginGoogle",
        openapi_extra=_esquema_json(CredencialGoogle),
        responses=respuestas_documentadas(
            {
                401: "ID token inválido",
                403: "Jugador no elegible",
                409: "Tipo de cuenta incompatible o estado de provisión inconsistente",
                413: "Cuerpo demasiado grande",
                415: "Se requiere application/json",
                422: "Solicitud inválida",
                503: "Identidad o provisión no disponible",
                500: "Error interno",
            }
        ),
    )
    async def login_google(request: Request, response: Response) -> RespuestaSesion:
        """Endpoint estándar de login Google para clientes web y móviles (200 OK)."""
        return await _intercambiar_google(request, response)

    @router.get(
        "/me",
        response_model=RespuestaPerfil,
        operation_id="getAuthenticatedProfile",
        summary="Obtener perfil del usuario autenticado y estado de juego",
        responses=respuestas_documentadas(
            {401: "Sesión requerida", 403: "Tipo de cuenta incompatible",
             503: "Identidad no disponible"},
        ),
    )
    async def obtener_mi_perfil(
        principal: Principal = Depends(autenticar),
    ) -> RespuestaPerfil:
        """Devuelve los datos de la cuenta y el perfil de jugador desde PostgreSQL."""
        try:
            perfil = await servicio().obtener_perfil(principal.id)
            return RespuestaPerfil(
                user_id=perfil.user_id,
                email=perfil.email,
                role=principal.rol,
                elo=perfil.elo,
                cubes=perfil.cubes,
                has_received_initial_collection=perfil.has_received_initial_collection,
                created_at=perfil.created_at,
            )
        except IdentidadNoDisponible:
            raise problema(503, "identidad_no_disponible", "Identidad no disponible.") from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None

    return router


def _respuesta_sesion(sesion: SesionEmitida, response: Response) -> RespuestaSesion:
    response.headers["Cache-Control"] = "no-store"
    return RespuestaSesion(
        access_token=sesion.token,
        expires_in=sesion.expira_en,
        user_id=sesion.principal.id,
        role=sesion.principal.rol,
        email=sesion.principal.email,
        is_new_user=sesion.is_new_user,
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
