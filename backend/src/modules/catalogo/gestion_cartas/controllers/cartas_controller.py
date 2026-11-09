"""Adaptador HTTP de Crear y Buscar Cartas."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect

from src.shared.http_module import problema, respuestas_documentadas
from src.shared.validacion.cuerpo import CuerpoExcesivo, flujo_acotado

from ..adapters.mongo_carta_repository import MongoCartaRepository
from ..domain.carta_model import DatosCarta
from ..domain.imagen_model import MAX_IMAGE_BYTES
from ..ports.cartas_ports import ErrorPersistencia
from ..services.cartas_service import (
    ActorCreacion,
    CartasService,
    CrearCarta,
    ErrorCreacion,
    SolicitudCrearCarta,
    TipoErrorCreacion,
)
from .cartas_dtos import (
    CamposCrearCarta,
    CartaCreada,
    CartaResponseDTO,
    CartaSearchQueryDTO,
    CartaSearchResponseDTO,
    HabilidadSeleccionable,
    esquema_multipart,
)

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
    habilidades: Callable[[], Awaitable[list[tuple[str, str]]]],
    jugador: Callable[..., Awaitable[Any]] | None = None,
) -> APIRouter:
    """Registra la creación y consulta de cartas con autorización de plataforma."""
    router = APIRouter(prefix="/content", tags=["Content Cards"])
    auth_jugador = jugador if jugador is not None else administrador

    @router.get(
        "/abilities",
        operation_id="listCardAbilities",
        responses=respuestas_documentadas(
            {
                401: "Sesión requerida",
                403: "Rol insuficiente",
                503: "Catálogo no disponible",
            }
        ),
    )
    async def listar_habilidades(_: str = Depends(administrador)) -> list[HabilidadSeleccionable]:
        """Devuelve solo las opciones necesarias para seleccionar una habilidad."""
        try:
            return [
                HabilidadSeleccionable(code=codigo, name=nombre)
                for codigo, nombre in await habilidades()
            ]
        except ErrorPersistencia:
            raise problema(503, "catalogo_no_disponible", "Catálogo no disponible.") from None

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
            status_code, detalle = _ERRORES[error.tipo]
            raise problema(status_code, error.tipo.value, detalle) from None
        except Exception:
            raise problema(500, "error_interno", "La solicitud no se pudo completar.") from None
        response.headers["X-Correlation-ID"] = resultado.operacion_id
        return CartaCreada.desde_resultado(resultado)

    @router.get(
        "/cards",
        response_model=CartaSearchResponseDTO,
        status_code=status.HTTP_200_OK,
        summary="Buscar y filtrar cartas del catálogo",
        description="Búsquedas rápidas optimizadas con MongoDB por texto, tipo y rareza.",
        responses=respuestas_documentadas({401: "Sesión requerida"}),
    )
    async def buscar_cartas(
        q: Annotated[str | None, Query(description="Nombre, código o texto descriptivo")] = None,
        tipo: Annotated[str | None, Query(description="Tipo elemental (ej. FUE, AGU)")] = None,
        rareza: Annotated[str | None, Query(description="Rareza (COMUN, RARA, etc.)")] = None,
        limite: Annotated[int, Query(ge=1, le=100, description="Cartas por página")] = 15,
        pagina: Annotated[int, Query(ge=1, description="Número de página")] = 1,
        _actor: Any = Depends(auth_jugador),
    ) -> CartaSearchResponseDTO:
        repo = MongoCartaRepository()
        srv = CartasService(repository=repo)
        search_params = CartaSearchQueryDTO(
            q=q,
            tipo=tipo,  # type: ignore[arg-type]
            rareza=rareza,  # type: ignore[arg-type]
            limite=limite,
            pagina=pagina,
        )
        return await srv.buscar_cartas(search_params)

    @router.get(
        "/cards/{identificador}",
        response_model=CartaResponseDTO,
        status_code=status.HTTP_200_OK,
        summary="Obtener detalle de carta por ID o Código",
        responses=respuestas_documentadas({401: "Sesión requerida", 404: "Carta no encontrada"}),
    )
    async def obtener_detalle_carta(
        identificador: str,
        _actor: Any = Depends(auth_jugador),
    ) -> CartaResponseDTO:
        repo = MongoCartaRepository()
        srv = CartasService(repository=repo)
        carta = await srv.obtener_detalle_carta(identificador)
        if not carta:
            raise problema(
                404, "carta_no_encontrada", f"No se encontró carta '{identificador}'."
            )
        return carta

    return router
