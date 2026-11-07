"""Adaptador HTTP de Crear Carta. La creación y sus transacciones pertenecen a 1D."""

from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import ValidationError
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect

from src.shared.http_module import problema, respuestas_documentadas
from src.shared.validacion.cuerpo import CuerpoExcesivo, flujo_acotado

from ..domain.carta_model import DatosCarta
from ..domain.imagen_model import MAX_IMAGE_BYTES
from ..services.cartas_service import (
    ActorCreacion,
    CrearCarta,
    ErrorCreacion,
    SolicitudCrearCarta,
    TipoErrorCreacion,
)
from .cartas_dtos import CamposCrearCarta, CartaCreada, esquema_multipart

_LIMITE_MULTIPART = MAX_IMAGE_BYTES + 16_384
_PATRON_CLAVE = r"^[!-+\x2D-~]{1,128}$"  # ASCII visible, sin coma (headers combinados).
_ERRORES = {
    TipoErrorCreacion.DATOS_INVALIDOS: (422, "Los datos de la carta no son válidos."),
    TipoErrorCreacion.HABILIDAD_INEXISTENTE: (404, "La habilidad no existe."),
    TipoErrorCreacion.EVOLUCION_INVALIDA: (422, "La evolución no es válida."),
    TipoErrorCreacion.CODIGO_AGOTADO: (409, "El tipo agotó sus códigos."),
    TipoErrorCreacion.CONFLICTO_IDEMPOTENCIA: (409, "La clave corresponde a otro contenido."),
    TipoErrorCreacion.EN_CURSO: (409, "La operación está en curso. Repite con la misma clave."),
    TipoErrorCreacion.RESERVA_INCOMPATIBLE: (409, "La operación requiere conciliación."),
    TipoErrorCreacion.RESULTADO_INCOMPATIBLE: (409, "El resultado requiere conciliación."),
    TipoErrorCreacion.RESERVA_INCIERTA: (409, "La reserva requiere conciliación."),
    TipoErrorCreacion.COMPENSACION_PENDIENTE: (
        409,
        "La operación está bloqueada por recuperación.",
    ),
    TipoErrorCreacion.IMAGEN_INVALIDA: (422, "La imagen no cumple los requisitos."),
    TipoErrorCreacion.IMAGEN_INCONSISTENTE: (409, "Los medios requieren conciliación."),
    TipoErrorCreacion.PROCESAMIENTO: (500, "La imagen no pudo procesarse."),
    TipoErrorCreacion.ALMACENAMIENTO: (503, "El almacenamiento no está disponible."),
    TipoErrorCreacion.TRANSACCION: (503, "No se pudo confirmar la operación."),
    TipoErrorCreacion.COMMIT_INCIERTO: (503, "Resultado incierto. Repite con la misma clave."),
}


def _demasiado_grande() -> HTTPException:
    return problema(413, "imagen_demasiado_grande", "El archivo supera el tamaño permitido.")


class _MultipartExcesivo(MultiPartException):
    """Interrumpe el parser y activa su cierre de archivos temporales."""


async def _flujo_multipart(request: Request) -> AsyncGenerator[bytes, None]:
    """Activa el cierre del parser cuando el flujo se excede o se interrumpe."""
    try:
        async for fragmento in flujo_acotado(request, _LIMITE_MULTIPART):
            yield fragmento
    except CuerpoExcesivo:
        raise _MultipartExcesivo("Límite multipart") from None
    except ClientDisconnect:
        raise MultiPartException("Solicitud interrumpida") from None


class _ParserCompleto(MultiPartParser):
    """Exige la frontera final, incluso si el parser ya completó los campos."""

    _completo = False

    def on_end(self) -> None:
        """Registra que se leyó la frontera final."""
        self._completo = True

    async def parse(self) -> FormData:
        """Cierra los temporales si faltó la frontera final."""
        formulario = await super().parse()
        if not self._completo:
            await formulario.close()
            raise MultiPartException("Cuerpo multipart incompleto")
        return formulario


async def _leer_solicitud(request: Request, clave: str) -> SolicitudCrearCarta:
    """Limita el cuerpo y la lectura del archivo y cierra temporales al salir."""
    tipo = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if tipo != "multipart/form-data":
        raise problema(415, "multipart_requerido", "Usa multipart/form-data.")
    try:
        formulario = await _ParserCompleto(
            request.headers,
            _flujo_multipart(request),
            max_files=1,
            max_fields=6,
            max_part_size=2048,
        ).parse()
    except _MultipartExcesivo:
        raise _demasiado_grande() from None
    except (MultiPartException, MultipartParseError):
        raise problema(422, "multipart_invalido", "Verifica los campos y el archivo.") from None

    try:
        partes = formulario.multi_items()
        if len(partes) != len(formulario):
            raise problema(422, "multipart_invalido", "Los campos no pueden repetirse.")
        archivo = formulario.get("image")
        if not isinstance(archivo, UploadFile):
            raise problema(422, "imagen_requerida", "Se requiere un archivo original.")
        try:
            dto = CamposCrearCarta.model_validate({k: v for k, v in partes if k != "image"})
        except ValidationError:
            raise problema(422, "solicitud_invalida", "Verifica los campos de la carta.") from None
        original = await archivo.read(MAX_IMAGE_BYTES + 1)
        if len(original) > MAX_IMAGE_BYTES:
            raise _demasiado_grande()
    finally:
        await formulario.close()
    return SolicitudCrearCarta(
        clave,
        DatosCarta(dto.name, dto.cost, dto.power, dto.card_type, dto.rarity, dto.ability_code),
        original,
    )


def crear_router(
    administrador: Callable[..., Awaitable[str]],
    servicio: Callable[[], CrearCarta],
) -> APIRouter:
    """Registra la creación con autorización obligatoria y composición diferida."""
    router = APIRouter(prefix="/content", tags=["Content Cards"])

    @router.post(
        "/cards",
        status_code=201,
        operation_id="createCard",
        description="Crea la carta con ambas imágenes verificadas. Un replay conserva el 201.",
        openapi_extra={"requestBody": esquema_multipart()},
        responses={
            201: {"headers": {"X-Correlation-ID": {"schema": {"type": "string"}}}},
            **respuestas_documentadas(
                {
                    401: "Sesión requerida",
                    403: "Rol insuficiente",
                    404: "Habilidad inexistente",
                    409: "Conflicto, operación en curso o conciliación requerida",
                    413: "Imagen o cuerpo demasiado grande",
                    415: "Se requiere multipart/form-data",
                    422: "Solicitud o imagen inválida",
                    500: "Error interno",
                    503: "Infraestructura no disponible o confirmación incierta",
                }
            ),
        },
    )
    async def crear_carta(
        request: Request,
        response: Response,
        actor: str = Depends(administrador),
        clave: str = Header(alias="Idempotency-Key", pattern=_PATRON_CLAVE),
    ) -> CartaCreada:
        """Autentica antes de leer el cuerpo y delega la creación al servicio existente."""
        if len(request.headers.getlist("idempotency-key")) != 1:
            raise problema(422, "idempotencia_invalida", "Envía una sola clave de idempotencia.")
        solicitud = await _leer_solicitud(request, clave)
        try:
            resultado = await servicio().ejecutar(ActorCreacion(actor), solicitud)
        except ErrorCreacion as error:
            status, detalle = _ERRORES[error.tipo]
            raise problema(status, error.tipo.value, detalle) from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None
        response.headers["X-Correlation-ID"] = resultado.operacion_id
        return CartaCreada.desde_resultado(resultado)

    return router
