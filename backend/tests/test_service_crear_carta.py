"""Reglas y coordinación con PostgreSQL 16 y GridFS 7 desechables."""

import asyncio
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from bson import ObjectId
from gridfs import AsyncGridFSBucket
from pymongo.errors import AutoReconnect
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSessionTransaction

from src.modules.catalogo import catalogo_module as catalogo
from src.shared.idempotencia.models import IdempotencyRecordORM
from src.shared.outbox import OutboxEventORM
from tests.test_card_persistence import (
    SIN_HABILIDAD,
    CartaORM,
    ContadorORM,
    HabilidadORM,
    ImagenORM,
    SessionFactory,
    nueva_carta,
)
from tests.test_card_persistence import factory as factory
from tests.test_gridfs_image_storage import MongoPrueba, imagen_procesada, oid
from tests.test_gridfs_image_storage import mongo as mongo
from tests.test_image_processing import binario_imagen

app = catalogo.aplicacion_cartas
tipos = app.TipoErrorCreacion
sql = catalogo.persistencia_creacion
DatosCarta = catalogo.dominio_cartas.DatosCarta


def datos_validos() -> Any:
    """Usa el seed y límites válidos de costo y poder."""
    return DatosCarta("  Guardiana  ", 10, -20, "LUC", "RARA", "HAB-000")


def solicitud(**cambios: Any) -> Any:
    """Crea una solicitud distinta salvo cuando el escenario la reutiliza."""
    return app.SolicitudCrearCarta(
        str(uuid4()), replace(datos_validos(), **cambios), binario_imagen()
    )


def actor() -> Any:
    """Identidad de prueba confiable y exclusiva de la invocación."""
    return app.ActorCreacion(str(uuid4()))


@pytest.mark.parametrize(
    "cambios",
    [
        {"costo": -1},
        {"costo": 11},
        {"costo": True},
        {"poder": -21},
        {"poder": 21},
        {"tipo": "luc"},
        {"rareza": "RARO"},
        {"nombre": "  "},
        {"nombre": "x" * 101},
        {"habilidad": "HAB-0000"},
    ],
)
async def test_datos_invalidos_se_rechazan_antes_de_abrir_sql(cambios: dict[str, Any]) -> None:
    """Los rechazos de dominio no dependen de infraestructura."""
    coordinacion = AsyncMock()
    servicio = app.CrearCarta(coordinacion, None, None)
    with pytest.raises(app.ErrorCreacion) as error:
        await servicio.ejecutar(actor(), solicitud(**cambios))
    assert error.value.tipo == tipos.DATOS_INVALIDOS
    coordinacion.exclusiva.assert_not_called()


def test_normalizacion_y_limite_de_codigo() -> None:
    """La normalización recorta el nombre y el contador se agota en 999."""
    dominio = catalogo.dominio_cartas
    assert datos_validos().normalizados().nombre == "Guardiana"
    assert dominio.siguiente_codigo("LUC", 998) == "PKA-LUC-999"
    with pytest.raises(dominio.CodigoAgotado):
        dominio.siguiente_codigo("LUC", 999)


@pytest.mark.parametrize("ruta", [(), ("nueva",), ("otra", "otra")])
async def test_habilidad_de_evolucion_invalida(ruta: tuple[str, ...]) -> None:
    """Rechaza destino ausente, autorreferencia y ciclo en el puerto de lectura."""
    cartas = AsyncMock()
    cartas.buscar_habilidad_por_codigo.return_value.evolution_target_card_id = "destino"
    cartas.ruta_evolucion.return_value = ruta
    with pytest.raises(app.ErrorCreacion) as error:
        await app._habilidad(cartas, "HAB-123", "nueva")
    assert error.value.tipo == tipos.EVOLUCION_INVALIDA


@dataclass
class Estado:
    """Filas observables por conexión independiente, después de cada intento."""

    reserva: IdempotencyRecordORM | None
    imagen: Any
    carta: Any
    evento: OutboxEventORM | None


async def estado(factory: SessionFactory, identidad: Any, peticion: Any) -> Estado:
    """Lee las filas de la operación y su resultado con la sesión oficial."""
    async with factory() as sesion:
        reserva = await sesion.scalar(
            select(IdempotencyRecordORM).where(
                IdempotencyRecordORM.actor_id == identidad.id,
                IdempotencyRecordORM.operation == "POST:/api/v1/content/cards",
                IdempotencyRecordORM.idempotency_key == peticion.clave_idempotencia,
            )
        )
        if reserva is None:
            return Estado(None, None, None, None)
        return Estado(
            reserva,
            await sesion.get(ImagenORM, reserva.id),
            await sesion.get(CartaORM, reserva.id),
            await sesion.get(OutboxEventORM, reserva.id),
        )


async def contador(factory: SessionFactory, tipo: str = "LUC") -> int:
    """Lee el último consecutivo confirmado de un tipo."""
    async with factory() as sesion:
        return cast(
            int,
            await sesion.scalar(
                select(ContadorORM.last_value).where(ContadorORM.card_type == tipo)
            ),
        )


def pendiente(filas: Estado, categoria: str | None) -> Any:
    """Comprueba los efectos permitidos de una operación no confirmada."""
    assert filas.carta is None and filas.evento is None
    assert filas.reserva and filas.reserva.response_status is None
    assert filas.reserva.response_body is None
    assert filas.reserva.resource_id == filas.imagen.id
    assert filas.imagen.state == ("PENDING" if categoria is None else "RETRY_PENDING")
    assert filas.imagen.sanitized_error == categoria
    return filas.imagen


async def test_creacion_completa_repeticion_conflicto_y_alcance(
    mongo: MongoPrueba, factory: SessionFactory
) -> None:
    """Verifica ambos motores y una clave reutilizada por otro actor."""
    servicio = catalogo.crear_servicio_crear_carta()
    identidad, peticion = actor(), solicitud()
    anterior = await contador(factory)
    resultado = await servicio.ejecutar(identidad, peticion)
    filas = await estado(factory, identidad, peticion)
    assert filas.reserva and filas.evento
    assert filas.reserva.response_status == 201
    assert filas.reserva.response_body is not None
    assert filas.reserva.response_body["id"] == resultado.carta_id
    assert resultado.carta_id == filas.carta.id == filas.imagen.id == filas.carta.image_id
    assert filas.carta.ability_id == SIN_HABILIDAD
    assert filas.carta.name == "Guardiana"
    assert filas.carta.code == resultado.codigo == f"PKA-LUC-{anterior + 1:03d}"
    assert filas.imagen.state == resultado.estado_imagen == "READY"
    assert filas.evento.event_type == "CardCreated" and filas.evento.status == "PENDING"
    assert filas.evento.aggregate_id == filas.evento.correlation_id == resultado.operacion_id
    assert filas.evento.payload["payload"]["image_status"] == "READY"
    assert filas.evento.payload["payload"]["ability_code"] == "HAB-000"
    modelo = catalogo.dominio_imagenes
    imagen = filas.imagen
    refs = modelo.ReferenciasImagen(imagen.original_storage_key, imagen.thumbnail_storage_key)
    assert await mongo.almacen.recuperar(refs.original) == peticion.original
    assert imagen.original_sha256 == hashlib.sha256(peticion.original).hexdigest()
    await mongo.almacen.verificar_par(
        modelo.ImagenAlmacenada(
            refs,
            modelo.MetadatosImagen(
                modelo.FormatoImagen(imagen.image_format),
                imagen.width,
                imagen.height,
                imagen.byte_size,
                imagen.original_sha256,
            ),
            modelo.MetadatosImagen(
                modelo.FormatoImagen(imagen.thumbnail_format),
                imagen.thumbnail_width,
                imagen.thumbnail_height,
                imagen.thumbnail_byte_size,
            ),
        )
    )
    limpia = replace(peticion, datos=replace(peticion.datos, nombre="Guardiana"))
    repetida = await catalogo.crear_servicio_crear_carta().ejecutar(identidad, limpia)
    assert repetida == replace(resultado, repetida=True)
    for distinta in (
        replace(peticion, datos=replace(peticion.datos, costo=9)),
        replace(peticion, original=binario_imagen("JPEG")),
    ):
        with pytest.raises(app.ErrorCreacion) as conflicto:
            await servicio.ejecutar(identidad, distinta)
        assert conflicto.value.tipo == tipos.CONFLICTO_IDEMPOTENCIA
    assert await contador(factory) == anterior + 1
    otro = await servicio.ejecutar(actor(), peticion)
    assert otro.carta_id != resultado.carta_id
    assert await contador(factory) == anterior + 2
    async with factory() as sesion:
        assert (
            await sesion.scalar(
                select(func.count()).select_from(HabilidadORM).where(HabilidadORM.code == "HAB-000")
            )
            == 1
        )


@pytest.mark.parametrize(
    ("habilidad", "binario", "categoria"),
    [("HAB-999", b"", "habilidad_inexistente"), ("HAB-000", b"invalid", "imagen_invalida")],
)
async def test_rechazo_sin_reserva(
    mongo: MongoPrueba, factory: SessionFactory, habilidad: str, binario: bytes, categoria: str
) -> None:
    """Los rechazos de habilidad y formato no reservan filas ni escriben GridFS."""
    identidad, peticion = actor(), solicitud(habilidad=habilidad)
    if binario:
        peticion = replace(peticion, original=binario)
    archivos = mongo.db["card_assets.files"]
    antes = await archivos.count_documents({})
    ultimo = await contador(factory)
    with pytest.raises(app.ErrorCreacion) as error:
        await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
    assert error.value.tipo == categoria and error.value.operacion_id is None
    assert (await estado(factory, identidad, peticion)).reserva is None
    assert await archivos.count_documents({}) == antes
    assert await contador(factory) == ultimo


async def test_capacidad_del_contador_no_reserva(
    mongo: MongoPrueba, factory: SessionFactory
) -> None:
    """El agotamiento se traduce a un error de negocio sin reservar la operación."""
    identidad, peticion = actor(), solicitud(tipo="PSI")
    ultimo = await contador(factory, "PSI")
    fila = update(ContadorORM).where(ContadorORM.card_type == "PSI")
    async with factory() as sesion, sesion.begin():
        await sesion.execute(fila.values(last_value=999))
    try:
        with pytest.raises(app.ErrorCreacion) as error:
            await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
        assert error.value.tipo == tipos.CODIGO_AGOTADO
        assert (await estado(factory, identidad, peticion)).reserva is None
        assert await contador(factory, "PSI") == 999
    finally:
        async with factory() as sesion, sesion.begin():
            await sesion.execute(fila.values(last_value=ultimo))


async def test_cte_detecta_ciclo_en_postgresql(factory: SessionFactory) -> None:
    """Ejecuta CYCLE sobre relaciones reales, con rollback al salir de la prueba."""
    async with factory() as sesion, sesion.begin():
        repositorio = catalogo.crear_repositorio_cartas(sesion)
        carta = nueva_carta(code="PKA-PSI-998", card_type="PSI")
        habilidad_id = str(uuid4())
        await repositorio.agregar(carta)
        sesion.add(
            HabilidadORM(
                id=habilidad_id,
                code="HAB-987",
                name="Evolución de prueba",
                ability_type="HAB-987",
                description="Prueba de evolución",
                params={},
                has_effect=True,
                evolution_target_card_id=carta.id,
            )
        )
        await sesion.flush()
        assert (await app._habilidad(repositorio, "HAB-987", "nueva")).id == habilidad_id
        await sesion.execute(
            update(CartaORM).where(CartaORM.id == carta.id).values(ability_id=habilidad_id)
        )
        assert await repositorio.ruta_evolucion(carta.id) == (carta.id, carta.id)
        with pytest.raises(app.ErrorCreacion) as error:
            await app._habilidad(repositorio, "HAB-987", "nueva")
        assert error.value.tipo == tipos.EVOLUCION_INVALIDA
        await sesion.rollback()


async def test_concurrencia_iguales_e_independientes(
    mongo: MongoPrueba, factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mantiene la primera invocación en GridFS y compite desde otras sesiones."""
    identidad, peticion = actor(), solicitud()
    entro, continuar = asyncio.Event(), asyncio.Event()
    clase = type(mongo.almacen)
    guardar = clase.guardar_par
    servicio = catalogo.crear_servicio_crear_carta()
    antes = await contador(factory)

    async def espera(almacen: Any, refs: Any, preparada: Any) -> Any:
        if not entro.is_set():
            entro.set()
            await asyncio.wait_for(continuar.wait(), 10)
        return await guardar(almacen, refs, preparada)

    monkeypatch.setattr(clase, "guardar_par", espera)
    async with asyncio.timeout(15), asyncio.TaskGroup() as grupo:
        primera = grupo.create_task(servicio.ejecutar(identidad, peticion))
        await entro.wait()
        with pytest.raises(app.ErrorCreacion) as ocupada:
            await servicio.ejecutar(identidad, peticion)
        assert ocupada.value.tipo == tipos.EN_CURSO
        pendiente(await estado(factory, identidad, peticion), None)
        assert await contador(factory) == antes
        async with factory() as sesion:
            assert (
                await sesion.scalar(
                    text(
                        "SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid "
                        "WHERE l.locktype='advisory' AND l.granted "
                        "AND a.datname=current_database() AND a.state='idle' "
                        "AND a.xact_start IS NULL"
                    )
                )
                == 1
            )
        segunda = grupo.create_task(servicio.ejecutar(identidad, solicitud()))
        tercera = grupo.create_task(servicio.ejecutar(identidad, solicitud()))
        continuar.set()
    assert {primera.result().codigo, segunda.result().codigo, tercera.result().codigo} == {
        f"PKA-LUC-{antes + i:03d}" for i in (1, 2, 3)
    }
    assert await contador(factory) == antes + 3
    assert (await servicio.ejecutar(identidad, peticion)).repetida
    assert await contador(factory) == antes + 3


@pytest.mark.parametrize("fase", ["original", "miniatura", "verificacion"])
async def test_fallo_de_medios_y_compensacion(
    mongo: MongoPrueba, factory: SessionFactory, monkeypatch: pytest.MonkeyPatch, fase: str
) -> None:
    """Persiste evidencia de parciales, preserva archivos ajenos y permite repetir."""
    identidad, peticion = actor(), solicitud()
    servicio = catalogo.crear_servicio_crear_carta()
    antes = await contador(factory)
    clase = type(mongo.almacen)
    verificar = clase.verificar_par
    subir = AsyncGridFSBucket.upload_from_stream_with_id
    borrar = AsyncGridFSBucket.delete
    chunks = mongo.db["card_assets.chunks"]
    ajenas = mongo.almacen.reservar()
    await mongo.almacen.guardar_par(ajenas, imagen_procesada())

    async def fallar_subida(
        bucket: AsyncGridFSBucket, file_id: ObjectId, nombre: str, datos: bytes
    ) -> None:
        if fase == "original" and nombre == "original":
            raise AutoReconnect("fallo simulado")
        if fase == "miniatura" and nombre == "thumbnail.webp":
            await chunks.insert_one({"files_id": file_id, "n": 0, "data": datos[:16]})
            raise AutoReconnect("fallo simulado")
        await subir(bucket, file_id, nombre, datos)

    async def corromper(almacen: Any, imagen: Any) -> None:
        await chunks.delete_one({"files_id": oid(imagen.referencias.miniatura), "n": 0})
        await verificar(almacen, imagen)

    with monkeypatch.context() as contexto:
        contexto.setattr(AsyncGridFSBucket, "upload_from_stream_with_id", fallar_subida)
        if fase == "verificacion":
            contexto.setattr(clase, "verificar_par", corromper)
        with pytest.raises(app.ErrorCreacion) as error:
            await servicio.ejecutar(identidad, peticion)
    categoria = tipos.IMAGEN_INCONSISTENTE if fase == "verificacion" else tipos.ALMACENAMIENTO
    assert error.value.tipo == categoria
    imagen = pendiente(await estado(factory, identidad, peticion), categoria)
    ids = [oid(imagen.original_storage_key), oid(imagen.thumbnail_storage_key)]
    assert (
        await mongo.db["card_assets.files"].count_documents({"_id": {"$in": ids}})
        == {
            "original": 0,
            "miniatura": 1,
            "verificacion": 2,
        }[fase]
    )
    if fase == "miniatura":
        assert error.value.confirmadas == (imagen.original_storage_key,)
        assert await chunks.count_documents({"files_id": ids[1]}) == 1

        async def fallar_borrado(bucket: AsyncGridFSBucket, file_id: ObjectId) -> None:
            if file_id == ids[1]:
                raise AutoReconnect("borrado interrumpido")
            await borrar(bucket, file_id)

        with monkeypatch.context() as contexto:
            contexto.setattr(AsyncGridFSBucket, "delete", fallar_borrado)
            with pytest.raises(app.ErrorCreacion) as limpieza:
                await servicio.compensar(identidad, peticion.clave_idempotencia)
        assert limpieza.value.tipo == tipos.ALMACENAMIENTO
        pendiente(await estado(factory, identidad, peticion), "compensacion_pendiente")
        assert await chunks.count_documents({"files_id": ids[1]}) == 1
    assert await contador(factory) == antes
    await servicio.compensar(identidad, peticion.clave_idempotencia, reanudar=fase == "miniatura")
    assert await chunks.count_documents({"files_id": {"$in": ids}}) == 0
    assert await mongo.almacen.recuperar(ajenas.original) == imagen_procesada().original.datos
    recuperada = await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
    assert recuperada.operacion_id == imagen.id
    assert await mongo.db["card_assets.files"].count_documents({"_id": {"$in": ids}}) == 2
    assert await contador(factory) == antes + 1
    with pytest.raises(app.ErrorCreacion) as protegida:
        await servicio.compensar(identidad, peticion.clave_idempotencia)
    assert protegida.value.tipo == tipos.RESERVA_INCOMPATIBLE
    assert await mongo.db["card_assets.files"].count_documents({"_id": {"$in": ids}}) == 2


@pytest.mark.parametrize("fase", ["carta", "outbox"])
async def test_rollback_sql_y_reintento(
    mongo: MongoPrueba, factory: SessionFactory, monkeypatch: pytest.MonkeyPatch, fase: str
) -> None:
    """Dispara CHECK de carta o PK de Outbox reales dentro de la confirmación."""
    async with factory() as sesion:
        repo = type(catalogo.crear_repositorio_cartas(sesion))
    agregar = repo.agregar
    evento = sql.SqlTransaccionCreacion.agregar_evento
    identidad, peticion = actor(), solicitud()
    servicio = catalogo.crear_servicio_crear_carta()
    antes = await contador(factory)

    async def carta_invalida(repositorio: Any, carta: Any) -> None:
        await agregar(repositorio, replace(carta, cost=11))

    async def evento_duplicado(tx: Any, carta: Any, payload: dict[str, str | int]) -> None:
        await evento(tx, carta, payload)
        await evento(tx, carta, payload)

    with monkeypatch.context() as contexto:
        if fase == "carta":
            contexto.setattr(repo, "agregar", carta_invalida)
        else:
            contexto.setattr(sql.SqlTransaccionCreacion, "agregar_evento", evento_duplicado)
        with pytest.raises(app.ErrorCreacion) as error:
            await servicio.ejecutar(identidad, peticion)
    assert error.value.tipo == tipos.TRANSACCION
    imagen = pendiente(await estado(factory, identidad, peticion), tipos.TRANSACCION)
    assert await contador(factory) == antes
    resultado = await servicio.ejecutar(identidad, peticion)
    assert resultado.operacion_id == imagen.id and await contador(factory) == antes + 1


@pytest.mark.parametrize("confirmado", [False, True])
async def test_commit_incierto_se_resuelve_con_lectura(
    mongo: MongoPrueba, factory: SessionFactory, monkeypatch: pytest.MonkeyPatch, confirmado: bool
) -> None:
    """Simula pérdida de respuesta antes o después de un commit real."""
    identidad, peticion = actor(), solicitud()
    antes = await contador(factory)
    confirmar = sql.SqlTransaccionCreacion.confirmar
    salir = AsyncSessionTransaction.__aexit__
    listo = False

    async def preparar(tx: Any, operacion_id: str, respuesta: dict[str, str | int]) -> None:
        nonlocal listo
        await confirmar(tx, operacion_id, respuesta)
        listo = True

    async def salida(tx: AsyncSessionTransaction, *exc: Any) -> None:
        nonlocal listo
        if not listo:
            await salir(tx, *exc)
            return
        listo = False
        if confirmado:
            await salir(tx, *exc)
        else:
            await tx.rollback()
            await salir(tx, *exc)
        raise OperationalError(None, None, RuntimeError("respuesta perdida"))

    with monkeypatch.context() as contexto:
        contexto.setattr(sql.SqlTransaccionCreacion, "confirmar", preparar)
        contexto.setattr(AsyncSessionTransaction, "__aexit__", salida)
        with pytest.raises(app.ErrorCreacion) as error:
            await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
    assert error.value.tipo == tipos.COMMIT_INCIERTO and error.value.reintentable
    filas = await estado(factory, identidad, peticion)
    assert filas.reserva and filas.reserva.id == error.value.operacion_id
    if confirmado:
        assert filas.carta and filas.evento and filas.imagen.state == "READY"
    else:
        pendiente(filas, None)
    refs = [oid(filas.imagen.original_storage_key), oid(filas.imagen.thumbnail_storage_key)]
    assert await mongo.db["card_assets.files"].count_documents({"_id": {"$in": refs}}) == 2
    resultado = await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
    assert resultado.repetida is confirmado
    assert resultado.operacion_id == error.value.operacion_id
    assert await contador(factory) == antes + 1


async def test_interrupcion_recuperada_por_nueva_instancia(
    mongo: MongoPrueba, factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancela tras escribir el par y recupera por IDs durables sin efectos repetidos."""
    identidad, peticion = actor(), solicitud()
    antes = await contador(factory)
    clase = type(mongo.almacen)
    verificar = clase.verificar_par

    async def interrumpir(almacen: Any, imagen: Any) -> None:
        await verificar(almacen, imagen)
        raise asyncio.CancelledError()

    with monkeypatch.context() as contexto:
        contexto.setattr(clase, "verificar_par", interrumpir)
        with pytest.raises(asyncio.CancelledError):
            await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
    imagen = pendiente(await estado(factory, identidad, peticion), None)
    ids = [oid(imagen.original_storage_key), oid(imagen.thumbnail_storage_key)]
    archivos = mongo.db["card_assets.files"]
    assert await archivos.count_documents({"_id": {"$in": ids}}) == 2
    assert await contador(factory) == antes
    recuperada = await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
    assert recuperada.operacion_id == imagen.id
    assert await archivos.count_documents({"_id": {"$in": ids}}) == 2
    assert await contador(factory) == antes + 1


@pytest.mark.parametrize("forma", ["historica", "array", "string", "null", "reserva_sin_datos"])
async def test_respuesta_historica_no_se_sobrescribe(
    mongo: MongoPrueba, factory: SessionFactory, forma: str
) -> None:
    """Una clave histórica con la huella original impide crear otra carta."""
    identidad, peticion = actor(), solicitud()
    recurso = str(uuid4())
    cuerpo: Any = {
        "historica": {"id": recurso, "code": "PKA-LUC-999", "image_status": "PENDING"},
        "array": [{"id": recurso}],
        "string": recurso,
        "null": JSONB.NULL,
        "reserva_sin_datos": None,
    }[forma]
    canon = {
        "name": "Guardiana",
        "cost": 10,
        "power": -20,
        "card_type": "LUC",
        "rarity": "RARA",
        "ability_code": "HAB-000",
        "image_sha256": hashlib.sha256(peticion.original).hexdigest(),
    }
    huella = hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode())
    antes = await contador(factory)
    async with factory() as sesion, sesion.begin():
        sesion.add(
            IdempotencyRecordORM(
                id=str(uuid4()),
                actor_id=identidad.id,
                operation="POST:/api/v1/content/cards",
                endpoint="POST:/api/v1/content/cards",
                idempotency_key=peticion.clave_idempotencia,
                request_hash=huella.hexdigest(),
                resource_id=recurso,
                response_status=None if forma == "reserva_sin_datos" else 201,
                response_body=cuerpo,
                created_at=datetime.now(UTC),
            )
        )
    with pytest.raises(app.ErrorCreacion) as error:
        await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
    assert error.value.tipo == (
        tipos.RESERVA_INCIERTA if forma == "reserva_sin_datos" else tipos.RESULTADO_INCOMPATIBLE
    )
    filas = await estado(factory, identidad, peticion)
    assert filas.reserva and filas.reserva.resource_id == recurso
    assert filas.reserva.response_body == (None if forma == "null" else cuerpo)
    assert filas.carta is None and filas.imagen is None and filas.evento is None
    assert await contador(factory) == antes


async def test_compensacion_con_sesion_perdida_no_permite_publicar(
    mongo: MongoPrueba, factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Termina la sesión real de limpieza mientras un DELETE de GridFS está suspendido."""
    identidad, peticion = actor(), solicitud()
    servicio = catalogo.crear_servicio_crear_carta()
    clase = type(mongo.almacen)
    verificar = clase.verificar_par
    borrar = AsyncGridFSBucket.delete
    listo, continuar = asyncio.Event(), asyncio.Event()
    antes = await contador(factory)

    async def interrumpir(almacen: Any, imagen: Any) -> None:
        await verificar(almacen, imagen)
        raise asyncio.CancelledError()

    async def pausar_borrado(bucket: AsyncGridFSBucket, file_id: ObjectId) -> None:
        listo.set()
        await continuar.wait()
        await borrar(bucket, file_id)

    async def limpiar() -> str | None:
        try:
            await servicio.compensar(identidad, peticion.clave_idempotencia)
        except app.ErrorCreacion as error:
            return str(error.tipo)
        return None

    with monkeypatch.context() as contexto:
        contexto.setattr(clase, "verificar_par", interrumpir)
        with pytest.raises(asyncio.CancelledError):
            await servicio.ejecutar(identidad, peticion)

    imagen = pendiente(await estado(factory, identidad, peticion), None)
    ids = [oid(imagen.original_storage_key), oid(imagen.thumbnail_storage_key)]
    archivos = mongo.db["card_assets.files"]
    filtro = {"_id": {"$in": ids}}
    assert await archivos.count_documents(filtro) == 2

    error_creacion = None
    error_compensacion = None
    with monkeypatch.context() as contexto:
        contexto.setattr(AsyncGridFSBucket, "delete", pausar_borrado)
        async with asyncio.timeout(15), asyncio.TaskGroup() as grupo:
            tarea = grupo.create_task(limpiar())
            await listo.wait()
            async with factory() as sesion:
                pids = (
                    await sesion.scalars(
                        text(
                            "SELECT DISTINCT l.pid FROM pg_locks l "
                            "JOIN pg_stat_activity a ON a.pid=l.pid "
                            "WHERE l.locktype='advisory' AND l.granted "
                            "AND a.datname=current_database()"
                        )
                    )
                ).all()
                assert len(pids) == 1
                assert await sesion.scalar(
                    text("SELECT pg_terminate_backend(:pid, 5000)"), {"pid": pids[0]}
                )
            try:
                await catalogo.crear_servicio_crear_carta().ejecutar(identidad, peticion)
            except app.ErrorCreacion as error:
                error_creacion = str(error.tipo)
            if error_creacion is not None:
                # El segundo limpiador tampoco puede apropiarse del bloqueo durable.
                error_compensacion = await limpiar()
            continuar.set()

    filas = await estado(factory, identidad, peticion)
    assert filas.carta is None, "El reintento publicó mientras un borrado previo seguía activo"
    assert error_creacion == tipos.COMPENSACION_PENDIENTE
    assert error_compensacion == tipos.COMPENSACION_PENDIENTE
    assert tarea.result() == tipos.TRANSACCION
    pendiente(filas, tipos.COMPENSACION_PENDIENTE)
    assert await archivos.count_documents(filtro) == 0
    assert await contador(factory) == antes
    # Ya han terminado la tarea anterior y sus dos comandos MongoDB.
    await servicio.compensar(identidad, peticion.clave_idempotencia, reanudar=True)
    resultado = await servicio.ejecutar(identidad, peticion)
    assert resultado.operacion_id == imagen.id
    assert await archivos.count_documents(filtro) == 2
    assert await contador(factory) == antes + 1


async def test_resultado_1d_discrepante_no_se_reproduce(
    mongo: MongoPrueba, factory: SessionFactory
) -> None:
    """Una respuesta con código plausible pero distinto de la carta se conserva."""
    identidad, peticion = actor(), solicitud()
    servicio = catalogo.crear_servicio_crear_carta()
    confirmada = await servicio.ejecutar(identidad, peticion)
    filas = await estado(factory, identidad, peticion)
    assert filas.reserva and filas.reserva.response_body is not None
    respuesta = filas.reserva.response_body | {"code": "PKA-LUC-999"}
    async with factory() as sesion, sesion.begin():
        await sesion.execute(
            update(IdempotencyRecordORM)
            .where(IdempotencyRecordORM.id == confirmada.operacion_id)
            .values(response_body=respuesta)
        )
    antes = await contador(factory)
    with pytest.raises(app.ErrorCreacion) as error:
        await servicio.ejecutar(identidad, peticion)
    assert error.value.tipo == tipos.RESULTADO_INCOMPATIBLE
    filas = await estado(factory, identidad, peticion)
    assert filas.reserva and filas.reserva.response_body == respuesta
    assert filas.carta.code == confirmada.codigo
    assert await contador(factory) == antes


async def test_compensacion_no_borra_si_el_commit_del_bloqueo_es_incierto(
    mongo: MongoPrueba, factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pierde la confirmación del bloqueo durable antes del primer borrado."""
    identidad, peticion = actor(), solicitud()
    servicio = catalogo.crear_servicio_crear_carta()
    clase = type(mongo.almacen)
    verificar = clase.verificar_par
    registrar_fallo = sql.SqlTransaccionCreacion.registrar_fallo
    salir = AsyncSessionTransaction.__aexit__
    marcado = False

    async def interrumpir(almacen: Any, imagen: Any) -> None:
        await verificar(almacen, imagen)
        raise asyncio.CancelledError()

    async def preparar(tx: Any, operacion_id: str, error: str, ahora: datetime) -> None:
        nonlocal marcado
        await registrar_fallo(tx, operacion_id, error, ahora)
        marcado = True

    async def perder_respuesta(tx: AsyncSessionTransaction, *exc: Any) -> None:
        nonlocal marcado
        await salir(tx, *exc)
        if marcado:
            marcado = False
            raise OperationalError(None, None, RuntimeError("respuesta perdida"))

    with monkeypatch.context() as contexto:
        contexto.setattr(clase, "verificar_par", interrumpir)
        with pytest.raises(asyncio.CancelledError):
            await servicio.ejecutar(identidad, peticion)

    antes = await contador(factory)
    with monkeypatch.context() as contexto:
        contexto.setattr(sql.SqlTransaccionCreacion, "registrar_fallo", preparar)
        contexto.setattr(AsyncSessionTransaction, "__aexit__", perder_respuesta)
        with pytest.raises(app.ErrorCreacion) as error:
            await servicio.compensar(identidad, peticion.clave_idempotencia)
    assert error.value.tipo == tipos.COMMIT_INCIERTO
    imagen = pendiente(await estado(factory, identidad, peticion), tipos.COMPENSACION_PENDIENTE)
    ids = [oid(imagen.original_storage_key), oid(imagen.thumbnail_storage_key)]
    assert await mongo.db["card_assets.files"].count_documents({"_id": {"$in": ids}}) == 2
    assert await contador(factory) == antes
    await servicio.compensar(identidad, peticion.clave_idempotencia, reanudar=True)
