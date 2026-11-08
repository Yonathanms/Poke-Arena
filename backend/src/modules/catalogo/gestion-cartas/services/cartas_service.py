"""Servicio Crear Carta. Coordina persistencia e imágenes sin transporte HTTP."""

import json
from asyncio import to_thread
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from re import fullmatch
from typing import Literal
from uuid import uuid4

from ..domain.carta_model import (
    Carta,
    CodigoAgotado,
    DatosCarta,
    DatosCartaInvalidos,
    Habilidad,
    siguiente_codigo,
)
from ..domain.imagen_model import (
    MAX_IMAGE_BYTES,
    ImagenAlmacenada,
    ReferenciasImagen,
    huella_imagen,
)
from ..ports.cartas_ports import CartasRepositoryPort, ErrorPersistencia
from ..ports.creacion_ports import (
    COMPENSACION_PENDIENTE,
    ClaveCreacion,
    ClaveOcupada,
    CommitIncierto,
    CoordinacionCreacionPort,
    OperacionCreacionPort,
    RegistroCreacion,
)
from ..ports.imagen_ports import (
    AlmacenImagenPort,
    ErrorAlmacenamiento,
    ErrorGuardadoPar,
    ErrorImagen,
    ErrorProcesamiento,
    ImagenInvalida,
    ProcesadorImagenPort,
)


@dataclass(frozen=True, slots=True)
class ActorCreacion:
    """Identidad ya autenticada por el llamador de confianza de la aplicación."""

    id: str


@dataclass(frozen=True, slots=True)
class SolicitudCrearCarta:
    """Datos de aplicación independientes de HTTP y bytes del único original."""

    clave_idempotencia: str
    datos: DatosCarta
    original: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ResultadoCrearCarta:
    """Creación confirmada, incluida la identidad durable de su operación."""

    carta_id: str
    codigo: str
    operacion_id: str
    imagen_id: str
    estado_imagen: Literal["READY"] = "READY"
    repetida: bool = False


class TipoErrorCreacion(StrEnum):
    """Clasificación consumible en Python y traducible por la futura API."""

    DATOS_INVALIDOS = "datos_invalidos"
    HABILIDAD_INEXISTENTE = "habilidad_inexistente"
    EVOLUCION_INVALIDA = "evolucion_invalida"
    CODIGO_AGOTADO = "codigo_agotado"
    CONFLICTO_IDEMPOTENCIA = "conflicto_idempotencia"
    EN_CURSO = "en_curso"
    RESERVA_INCOMPATIBLE = "reserva_incompatible"
    RESULTADO_INCOMPATIBLE = "resultado_incompatible"
    RESERVA_INCIERTA = "reserva_incierta"
    COMPENSACION_PENDIENTE = COMPENSACION_PENDIENTE
    IMAGEN_INVALIDA = "imagen_invalida"
    PROCESAMIENTO = "procesamiento_imagen"
    IMAGEN_INCONSISTENTE = "imagen_inconsistente"
    ALMACENAMIENTO = "almacenamiento"
    TRANSACCION = "transaccion"
    COMMIT_INCIERTO = "commit_incierto"


class ErrorCreacion(Exception):
    """Fallo sanitizado con identidad de la reserva si ya se conoce."""

    def __init__(
        self,
        tipo: TipoErrorCreacion,
        operacion_id: str | None = None,
        *,
        reintentable: bool = False,
        referencias: ReferenciasImagen | None = None,
        confirmadas: tuple[str, ...] = (),
    ) -> None:
        """Conserva solo datos técnicos necesarios para recuperar la operación."""
        super().__init__(tipo.value)
        self.tipo = tipo
        self.operacion_id = operacion_id
        self.reintentable = reintentable
        self.referencias = referencias
        self.confirmadas = confirmadas


def _clave(actor: ActorCreacion, clave: str) -> ClaveCreacion:
    """Valida los tamaños SQL sin normalizar el alcance de idempotencia."""
    if any(not valor.strip() or len(valor) > 128 or "\0" in valor for valor in (actor.id, clave)):
        raise ErrorCreacion(TipoErrorCreacion.DATOS_INVALIDOS)
    return ClaveCreacion(actor.id, clave)


def _huella(datos: DatosCarta, original: bytes) -> str:
    """Mantiene la forma canónica histórica e incluye el SHA-256 de los bytes."""
    canon = {
        "name": datos.nombre,
        "cost": datos.costo,
        "power": datos.poder,
        "card_type": datos.tipo,
        "rarity": datos.rareza,
        "ability_code": datos.habilidad,
        "image_sha256": huella_imagen(original),
    }
    return sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _reserva(registro: RegistroCreacion) -> ImagenAlmacenada:
    """Reconoce una reserva 1D sin interpretar registros históricos como pendientes."""
    if (
        registro.recurso != registro.id
        or registro.imagen is None
        or registro.estado_imagen not in ("PENDING", "RETRY_PENDING")
        or registro.estado_respuesta is not None
    ):
        raise ErrorCreacion(TipoErrorCreacion.RESERVA_INCOMPATIBLE, registro.id)
    return registro.imagen


def _resultado(registro: RegistroCreacion, huella: str, tipo: str) -> ResultadoCrearCarta | None:
    """Reproduce solo el snapshot confirmado de 1D y protege el alcance histórico."""
    if registro.huella != huella:
        raise ErrorCreacion(TipoErrorCreacion.CONFLICTO_IDEMPOTENCIA, registro.id)
    if registro.estado_respuesta is None:
        try:
            _reserva(registro)
        except ErrorCreacion:
            raise ErrorCreacion(TipoErrorCreacion.RESERVA_INCIERTA, registro.id) from None
        if registro.compensacion_pendiente:
            raise ErrorCreacion(TipoErrorCreacion.COMPENSACION_PENDIENTE, registro.id)
        return None
    cuerpo = registro.respuesta
    if not isinstance(cuerpo, dict):
        raise ErrorCreacion(TipoErrorCreacion.RESULTADO_INCOMPATIBLE, registro.id)
    codigo = cuerpo.get("code")
    if (
        registro.estado_respuesta != 201
        or cuerpo.get("contract") != "1D"
        or registro.recurso != registro.id
        or cuerpo.get("id") != registro.id
        or cuerpo.get("image_id") != registro.id
        or cuerpo.get("image_status") != "READY"
        or not isinstance(codigo, str)
        or codigo != registro.codigo_confirmado
        or fullmatch(rf"PKA-{tipo}-[0-9]{{3}}", codigo) is None
        or codigo.endswith("-000")
    ):
        raise ErrorCreacion(TipoErrorCreacion.RESULTADO_INCOMPATIBLE, registro.id)
    return ResultadoCrearCarta(registro.id, codigo, registro.id, registro.id, repetida=True)


def _error_imagen(error: ErrorImagen, operacion_id: str | None) -> ErrorCreacion:
    """Traduce errores de 1C sin perder las referencias de un resultado parcial."""
    parcial = error if isinstance(error, ErrorGuardadoPar) else None
    causa = parcial.causa if parcial is not None else error
    reintentable = False
    if isinstance(causa, ImagenInvalida):
        tipo = TipoErrorCreacion.IMAGEN_INVALIDA
    elif isinstance(causa, ErrorProcesamiento):
        tipo = TipoErrorCreacion.PROCESAMIENTO
    elif isinstance(causa, ErrorAlmacenamiento):
        tipo = TipoErrorCreacion.ALMACENAMIENTO
        reintentable = causa.reintentable
    else:
        tipo = TipoErrorCreacion.IMAGEN_INCONSISTENTE
    return ErrorCreacion(
        tipo,
        operacion_id,
        reintentable=reintentable,
        referencias=parcial.referencias if parcial else None,
        confirmadas=parcial.confirmadas if parcial else (),
    )


def _codigo_disponible(tipo: str, ultimo: int | None, operacion_id: str | None) -> tuple[str, int]:
    """Traduce un contador ausente o agotado sin asignar un código."""
    if ultimo is None:
        raise ErrorCreacion(TipoErrorCreacion.TRANSACCION, operacion_id)
    try:
        return siguiente_codigo(tipo, ultimo), ultimo + 1
    except CodigoAgotado:
        raise ErrorCreacion(TipoErrorCreacion.CODIGO_AGOTADO, operacion_id) from None


async def _habilidad(
    cartas: CartasRepositoryPort,
    codigo: str,
    operacion_id: str,
) -> Habilidad:
    """Exige habilidad existente y descarta rutas de evolución cíclicas."""
    habilidad = await cartas.buscar_habilidad_por_codigo(codigo)
    if habilidad is None:
        raise ErrorCreacion(TipoErrorCreacion.HABILIDAD_INEXISTENTE)
    destino = habilidad.evolution_target_card_id
    if destino is not None:
        ruta = await cartas.ruta_evolucion(destino)
        if not ruta or operacion_id in ruta or len(set(ruta)) != len(ruta):
            raise ErrorCreacion(TipoErrorCreacion.EVOLUCION_INVALIDA)
    return habilidad


class CrearCarta:
    """Caso de uso con reserva durable y confirmación SQL posterior a GridFS."""

    def __init__(
        self,
        coordinacion: CoordinacionCreacionPort,
        procesador: ProcesadorImagenPort,
        almacen: AlmacenImagenPort,
    ) -> None:
        """Recibe coordinación SQL y los puertos de medios de 1C."""
        self._coordinacion = coordinacion
        self._procesador = procesador
        self._almacen = almacen

    async def ejecutar(
        self,
        actor: ActorCreacion,
        solicitud: SolicitudCrearCarta,
    ) -> ResultadoCrearCarta:
        """Crea una carta o reproduce su resultado confirmado, sin efectos duplicados."""
        clave = _clave(actor, solicitud.clave_idempotencia)
        try:
            datos = solicitud.datos.normalizados()
        except DatosCartaInvalidos:
            raise ErrorCreacion(TipoErrorCreacion.DATOS_INVALIDOS) from None
        if not 0 < len(solicitud.original) <= MAX_IMAGE_BYTES:
            raise ErrorCreacion(TipoErrorCreacion.IMAGEN_INVALIDA)
        huella = _huella(datos, solicitud.original)
        operacion_id = None
        try:
            async with self._coordinacion.exclusiva(clave) as operacion:
                async with operacion.transaccion() as tx:
                    registro = await tx.obtener(clave)
                    if registro is not None:
                        operacion_id = registro.id
                        anterior = _resultado(registro, huella, datos.tipo)
                        if anterior is not None:
                            return anterior
                    candidato = registro.id if registro is not None else str(uuid4())
                    await _habilidad(tx.cartas, datos.habilidad, candidato)
                    ultimo = await tx.cartas.bloquear_contador(datos.tipo)
                    _codigo_disponible(datos.tipo, ultimo, operacion_id)

                procesada = await to_thread(self._procesador.procesar, solicitud.original)
                refs = (
                    _reserva(registro).referencias
                    if registro is not None
                    else self._almacen.reservar()
                )
                imagen = ImagenAlmacenada(
                    refs,
                    procesada.original.metadatos,
                    replace(procesada.miniatura.metadatos, sha256=None),
                )
                operacion_id = candidato
                async with operacion.transaccion() as tx:
                    if registro is None:
                        await tx.reservar(clave, operacion_id, huella, imagen, datetime.now(UTC))
                    else:
                        if _reserva(registro) != imagen:
                            raise ErrorCreacion(
                                TipoErrorCreacion.IMAGEN_INCONSISTENTE,
                                operacion_id,
                            )
                        await tx.registrar_intento(operacion_id, datetime.now(UTC))

                try:
                    guardada = await self._almacen.guardar_par(refs, procesada)
                    await self._almacen.verificar_par(guardada)
                    return await self._finalizar(
                        operacion, clave, huella, operacion_id, datos, imagen
                    )
                except CommitIncierto:
                    raise
                except (ErrorImagen, ErrorPersistencia, ErrorCreacion) as error:
                    if isinstance(error, ErrorImagen):
                        diagnostico = _error_imagen(error, operacion_id)
                    elif isinstance(error, ErrorCreacion):
                        diagnostico = error
                    else:
                        diagnostico = ErrorCreacion(
                            TipoErrorCreacion.TRANSACCION, operacion_id, reintentable=True
                        )
                    async with operacion.transaccion() as tx:
                        await tx.registrar_fallo(
                            operacion_id, diagnostico.tipo.value, datetime.now(UTC)
                        )
                    raise diagnostico from None
        except ClaveOcupada:
            raise ErrorCreacion(TipoErrorCreacion.EN_CURSO, reintentable=True) from None
        except CommitIncierto:
            raise ErrorCreacion(
                TipoErrorCreacion.COMMIT_INCIERTO,
                operacion_id,
                reintentable=True,
            ) from None
        except ErrorPersistencia:
            raise ErrorCreacion(
                TipoErrorCreacion.TRANSACCION,
                operacion_id,
                reintentable=True,
            ) from None
        except ErrorImagen as error:
            raise _error_imagen(error, operacion_id) from None

    async def _finalizar(
        self,
        operacion: OperacionCreacionPort,
        clave: ClaveCreacion,
        huella: str,
        operacion_id: str,
        datos: DatosCarta,
        imagen: ImagenAlmacenada,
    ) -> ResultadoCrearCarta:
        """Confirma código, imagen, carta, evento y respuesta bajo un solo BEGIN."""
        async with operacion.transaccion() as tx:
            registro = await tx.obtener(clave)
            if registro is None or registro.id != operacion_id:
                raise ErrorCreacion(TipoErrorCreacion.RESERVA_INCOMPATIBLE, operacion_id)
            anterior = _resultado(registro, huella, datos.tipo)
            if anterior is not None:
                return anterior
            if _reserva(registro) != imagen:
                raise ErrorCreacion(TipoErrorCreacion.RESERVA_INCOMPATIBLE, operacion_id)
            habilidad = await _habilidad(tx.cartas, datos.habilidad, operacion_id)
            ultimo = await tx.cartas.bloquear_contador(datos.tipo)
            codigo, consecutivo = _codigo_disponible(datos.tipo, ultimo, operacion_id)
            ahora = datetime.now(UTC)
            carta = Carta(
                id=operacion_id,
                image_id=operacion_id,
                code=codigo,
                name=datos.nombre,
                cost=datos.costo,
                power=datos.poder,
                card_type=datos.tipo,
                rarity=datos.rareza,
                ability_id=habilidad.id,
                created_at=ahora,
            )
            await tx.cartas.actualizar_contador(datos.tipo, consecutivo)
            await tx.marcar_lista(operacion_id, ahora)
            await tx.cartas.agregar(carta)
            respuesta: dict[str, str | int] = {
                "contract": "1D",
                "id": operacion_id,
                "code": codigo,
                "image_id": operacion_id,
                "image_status": "READY",
            }
            evento: dict[str, str | int] = {
                "id": carta.id,
                "code": carta.code,
                "image_id": operacion_id,
                "image_status": "READY",
                "name": carta.name,
                "cost": carta.cost,
                "power": carta.power,
                "card_type": carta.card_type,
                "rarity": carta.rarity,
                "ability_id": habilidad.id,
                "ability_code": habilidad.code,
            }
            await tx.agregar_evento(carta, evento)
            await tx.confirmar(operacion_id, respuesta)
        return ResultadoCrearCarta(operacion_id, codigo, operacion_id, operacion_id)

    async def compensar(
        self, actor: ActorCreacion, clave_idempotencia: str, *, reanudar: bool = False
    ) -> None:
        """Limpia una reserva con el bloqueo SQL confirmado antes de borrar.

        El operador debe haber drenado cualquier escritura previa de esta clave.
        Si ya existe un bloqueo durable, solo puede reanudar tras confirmar que
        el limpiador anterior y sus comandos MongoDB terminaron. La reserva
        conserva los mismos IDs incluso ante una respuesta de borrado incierta.
        """
        clave = _clave(actor, clave_idempotencia)
        operacion_id = None
        try:
            async with self._coordinacion.exclusiva(clave) as operacion:
                async with operacion.transaccion() as tx:
                    registro = await tx.obtener(clave)
                    if registro is None:
                        raise ErrorCreacion(TipoErrorCreacion.RESERVA_INCOMPATIBLE)
                    operacion_id = registro.id
                    imagen = _reserva(registro)
                    if not await tx.puede_compensar(operacion_id, imagen):
                        raise ErrorCreacion(TipoErrorCreacion.RESERVA_INCOMPATIBLE, operacion_id)
                    if registro.compensacion_pendiente:
                        if not reanudar:
                            raise ErrorCreacion(
                                TipoErrorCreacion.COMPENSACION_PENDIENTE, operacion_id
                            )
                    elif reanudar:
                        raise ErrorCreacion(TipoErrorCreacion.RESERVA_INCOMPATIBLE, operacion_id)
                    else:
                        await tx.registrar_fallo(
                            operacion_id, COMPENSACION_PENDIENTE, datetime.now(UTC)
                        )
                await self._almacen.eliminar(imagen.referencias.original)
                await self._almacen.eliminar(imagen.referencias.miniatura)
                async with operacion.transaccion() as tx:
                    await tx.terminar_compensacion(operacion_id, datetime.now(UTC))
        except ClaveOcupada:
            raise ErrorCreacion(TipoErrorCreacion.EN_CURSO, reintentable=True) from None
        except CommitIncierto:
            raise ErrorCreacion(
                TipoErrorCreacion.COMMIT_INCIERTO,
                operacion_id,
                reintentable=True,
            ) from None
        except ErrorPersistencia:
            raise ErrorCreacion(
                TipoErrorCreacion.TRANSACCION,
                operacion_id,
                reintentable=True,
            ) from None
        except ErrorImagen as error:
            raise _error_imagen(error, operacion_id) from None
