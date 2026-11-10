"""Contrato, concurrencia y recuperación de 1F sobre motores desechables."""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import AutoReconnect, OperationFailure
from pymongo.uri_parser import parse_uri
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSessionTransaction

from src.database.outbox_worker import verificar_configuracion
from src.modules.catalogo import catalogo_module as catalogo
from src.modules.identidad import identidad_module as identidad
from src.shared.config import Settings
from src.shared.outbox import OutboxEventORM
from tests.test_card_persistence import BACKEND, ImagenORM, SessionFactory
from tests.test_card_persistence import factory as factory
from tests.test_gridfs_image_storage import MongoPrueba
from tests.test_gridfs_image_storage import mongo as mongo
from tests.test_image_processing import binario_imagen
from tests.test_service_crear_carta import actor, solicitud
from tests.test_web_create_card import _app, _post

dominio = catalogo.proyeccion_domain
aplicacion = catalogo.outbox_app
Evento = OutboxEventORM


def evento() -> Any:
    """Sobre mínimo para probar validación y política sin abrir conexiones."""
    eid, agregado = str(uuid4()), str(uuid4())
    return dominio.EventoReclamado(
        eid,
        "CardCreated",
        agregado,
        1,
        1,
        eid,
        datetime.now(UTC),
        {
            "event_id": eid,
            "aggregate_id": agregado,
            "aggregate_version": 1,
            "schema_version": 1,
            "correlation_id": eid,
            "payload": {"id": agregado},
        },
        1,
        str(uuid4()),
    )


@pytest.mark.parametrize(
    "cambio",
    [
        {"tipo": "CardUpdated"},
        {"esquema": 2},
        {"version": 0},
        {"correlacion": None},
        {"sobre": []},
        {"sobre": {"payload": {}}},
        {"creado": datetime(2000, 1, 1)},
    ],
)
def test_eventos_invalidos(cambio: dict[str, Any]) -> None:
    """Valida tipo, versión, IDs, reloj y sobre antes de proyectar."""
    with pytest.raises(dominio.EventoIncompatible):
        replace(evento(), **cambio).contenido()


def test_evento_y_backoff() -> None:
    """Un evento válido expone su contenido y el backoff tiene tope."""
    ev = evento()
    assert ev.contenido() == {"id": ev.agregado}
    assert aplicacion.demora_reintento(1, 300) == 2
    assert aplicacion.demora_reintento(8, 300) == 256
    assert aplicacion.demora_reintento(999, 300) == 300


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("DATABASE_URL", "postgresql+asyncpg://app@localhost/pokearena_db"),
        ("MONGO_DB", "pokearena_catalog"),
        ("MONGO_URL", "mongodb://app@example.invalid/pokearena_outbox_demo"),
        ("OUTBOX_LEASE_SECONDS", 1),
    ],
)
def test_worker_rechaza_destino_y_lease_invalidos(campo: str, valor: str | int) -> None:
    """Rechaza configuraciones ajenas a pruebas y leases inferiores al timeout."""
    ajustes: dict[str, Any] = {
        "DATABASE_URL": "postgresql+asyncpg://app@localhost/pokearena_alembic_demo",
        "MONGO_URL": "mongodb://app@localhost/pokearena_outbox_demo",
        "MONGO_DB": "pokearena_outbox_demo",
    }
    with pytest.raises(ValueError, match="configuracion_outbox"):
        verificar_configuracion(Settings(_env_file=None, **(ajustes | {campo: valor})))


async def test_worker_no_reclama_despues_de_senal() -> None:
    """Permite acabar el grupo activo y deja de reclamar aunque quede presupuesto."""
    detener = asyncio.Event()
    reclamada = evento()
    repo = AsyncMock()
    repo.reclamar.return_value = [reclamada]
    repo.resolver.return_value = True
    mongo = AsyncMock()

    async def guardar(_: object) -> None:
        detener.set()

    mongo.guardar.side_effect = guardar
    assert await aplicacion.ProcesadorOutbox(repo, mongo, 300).lote(20, 4, detener) == 1
    repo.reclamar.assert_awaited_once_with(4)
    repo.resolver.assert_awaited_once_with(reclamada, None, None)


@pytest_asyncio.fixture(loop_scope="function")
async def proyeccion() -> AsyncIterator[Any]:
    """Conexión de prueba separada con permisos exclusivos sobre la proyección."""
    url = os.environ.get("MONGO_OUTBOX_TEST_URL")
    if not url:
        pytest.skip("Requiere MONGO_OUTBOX_TEST_URL en MongoDB 7 aislado")
    destino = parse_uri(url)
    base = destino["database"]
    assert destino["username"] == "projection_test" and destino["password"]
    assert isinstance(base, str) and base.startswith("pokearena_gridfs_test_")
    assert all(h == "127.0.0.1" and p != 27017 for h, p in destino["nodelist"])
    async with AsyncMongoClient[dict[str, Any]](url, timeoutMS=5000) as cliente:
        coleccion = cliente[base]["cards_projection"]
        almacen = catalogo.outbox_mongo.MongoProyeccionCartas(coleccion)
        await almacen.verificar_indices()
        yield SimpleNamespace(almacen=almacen, coleccion=coleccion, url=url, base=base)


async def crear_carta(mongo: MongoPrueba) -> Any:
    """Usa el caso 1D real y GridFS autenticado para producir el evento."""
    return await catalogo.crear_servicio_crear_carta().ejecutar(actor(), solicitud())


async def fila(factory: SessionFactory, id_evento: str) -> OutboxEventORM:
    """Consulta estado durable después de cerrar la transacción del worker."""
    async with factory() as sesion:
        valor = await sesion.get(Evento, id_evento)
        assert valor is not None
        return valor


async def cambiar(factory: SessionFactory, id_evento: str, **valores: object) -> None:
    """Inyecta reloj o estado de un evento sintético sin tocar otras filas."""
    async with factory() as sesion, sesion.begin():
        await sesion.execute(update(Evento).where(Evento.id == id_evento).values(**valores))


def componentes(factory: SessionFactory, almacen: Any, max_intentos: int = 8) -> tuple[Any, Any]:
    """Compone instancias independientes con fábrica de pruebas y lease acotado."""
    repo = catalogo.outbox_sql.SqlOutboxCartas(factory, 60, max_intentos)
    return repo, aplicacion.ProcesadorOutbox(repo, almacen, 300)


@pytest_asyncio.fixture(loop_scope="function")
async def cola_vacia(factory: SessionFactory, proyeccion: Any) -> None:
    """Consume el backlog de otras pruebas antes de medir una reclamación."""
    _, worker = componentes(factory, proyeccion.almacen)
    await worker.lote(500, 4, asyncio.Event())


async def test_cli_proyecta_creacion_y_reinicio(
    mongo: MongoPrueba, factory: SessionFactory, proyeccion: Any
) -> None:
    """La creación funciona sin proceso activo y el comando independiente la publica."""
    app = _app()

    async def admin() -> str:
        return "admin-aislado-1f"

    app.dependency_overrides[identidad.requerir_administrador] = admin
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        respuesta = await _post(cliente, str(uuid4()), imagen=binario_imagen())
    assert respuesta.status_code == 201
    id_carta = respuesta.json()["id"]
    assert (await fila(factory, id_carta)).status == "PENDING"
    assert await proyeccion.coleccion.find_one({"_id": id_carta}) is None

    async def ejecutar_cli(esperar_id: str | None = None) -> None:
        argumentos = ("--once",) if esperar_id is None else ()
        proceso = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "src.database.outbox_worker",
            *argumentos,
            cwd=BACKEND,
            env=os.environ
            | {
                "DATABASE_URL": os.environ["ORM_TEST_DATABASE_URL"],
                "ENVIRONMENT": "test",
                "MONGO_URL": proyeccion.url,
                "MONGO_DB": proyeccion.base,
                "OUTBOX_BATCH_SIZE": "500",
                "OUTBOX_POLL_SECONDS": "0.1",
                "DEBUG": "false",
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            if esperar_id is not None:
                async with asyncio.timeout(15):
                    while (await fila(factory, esperar_id)).status != "PROCESSED":
                        assert proceso.returncode is None
                        await asyncio.sleep(0.05)
                proceso.terminate()
            _, stderr = await asyncio.wait_for(proceso.communicate(), 30)
        finally:
            if proceso.returncode is None:
                proceso.kill()
                await proceso.wait()
        assert proceso.returncode == 0, stderr.decode()

    await ejecutar_cli()
    ev = await fila(factory, id_carta)
    assert ev.status == "PROCESSED" and ev.processed_at and ev.attempts == 1
    documento = await proyeccion.coleccion.find_one({"_id": id_carta})
    assert documento == ev.payload["payload"] | {
        "_id": id_carta,
        "aggregate_version": 1,
    }
    with pytest.raises(OperationFailure) as error:
        await proyeccion.coleccion.database["card_assets.files"].find_one()
    assert error.value.code == 13
    tardia = await crear_carta(mongo)
    await ejecutar_cli(tardia.carta_id)
    assert (await fila(factory, id_carta)).attempts == 1
    assert (await fila(factory, tardia.carta_id)).attempts == 1


@pytest.mark.usefixtures("cola_vacia")
async def test_concurrencia_reclamacion_y_fencing(
    mongo: MongoPrueba, factory: SessionFactory, proyeccion: Any
) -> None:
    """Workers reales compiten por filas y el token viejo no permite confirmar."""
    ids = {(await crear_carta(mongo)).carta_id for _ in range(4)}
    a, worker_a = componentes(factory, proyeccion.almacen)
    b, worker_b = componentes(factory, proyeccion.almacen)
    async with asyncio.timeout(15):
        assert (
            sum(
                await asyncio.gather(
                    worker_a.lote(2, 2, asyncio.Event()),
                    worker_b.lote(2, 2, asyncio.Event()),
                )
            )
            == 4
        )
    for id_carta in ids:
        ev = await fila(factory, id_carta)
        assert ev.attempts == 1 and ev.status == "PROCESSED"
    assert await proyeccion.coleccion.count_documents({"_id": {"$in": list(ids)}}) == 4

    resultado = await crear_carta(mongo)
    async with factory() as sesion, sesion.begin():
        await sesion.execute(
            select(Evento.id).where(Evento.id == resultado.carta_id).with_for_update()
        )
        assert await asyncio.wait_for(a.reclamar(1), 3) == []
    [viejo] = await a.reclamar(1)
    assert viejo.id == resultado.carta_id
    assert await b.reclamar(1) == []
    await cambiar(factory, viejo.id, lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert not await a.resolver(viejo, None)
    [nuevo] = await b.reclamar(1)
    assert nuevo.id == viejo.id and nuevo.token != viejo.token
    assert not await a.resolver(viejo, "error_obsoleto", 2)
    await proyeccion.almacen.guardar(await b.proyeccion(nuevo, nuevo.contenido()))
    assert await b.resolver(nuevo, None)
    assert (await fila(factory, viejo.id)).attempts == 2


@pytest.mark.usefixtures("cola_vacia")
async def test_mongo_falla_y_reintenta(
    mongo: MongoPrueba, factory: SessionFactory, proyeccion: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Traduce una indisponibilidad y respeta next_attempt_at antes de continuar."""
    resultado = await crear_carta(mongo)
    repo, worker = componentes(factory, proyeccion.almacen)

    async def desconectar(*args: Any, **kwargs: Any) -> None:
        raise AutoReconnect("detalle privado")

    with monkeypatch.context() as contexto:
        contexto.setattr(AsyncCollection, "update_one", desconectar)
        assert await worker.lote(1, 1, asyncio.Event()) == 0
    ev = await fila(factory, resultado.carta_id)
    assert ev.status == "RETRY_PENDING" and ev.sanitized_error == "dependencia_no_confirmada"
    assert ev.next_attempt_at and await repo.reclamar(1) == []
    assert await proyeccion.coleccion.find_one({"_id": ev.id}) is None
    await cambiar(factory, ev.id, next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
    assert await worker.lote(1, 1, asyncio.Event()) == 1
    assert (await fila(factory, ev.id)).attempts == 2


@pytest.mark.parametrize("confirmado", [False, True])
@pytest.mark.usefixtures("cola_vacia")
async def test_commit_confirmacion_incierto(
    mongo: MongoPrueba,
    factory: SessionFactory,
    proyeccion: Any,
    monkeypatch: pytest.MonkeyPatch,
    confirmado: bool,
) -> None:
    """Pierde la respuesta SQL antes o después del commit real de confirmación."""
    resultado = await crear_carta(mongo)
    repo, worker = componentes(factory, proyeccion.almacen)
    clase = type(proyeccion.almacen)
    guardar = clase.guardar
    salir = AsyncSessionTransaction.__aexit__
    pendiente = False

    async def escrita(almacen: Any, carta: Any) -> None:
        nonlocal pendiente
        await guardar(almacen, carta)
        pendiente = True

    async def salida(tx: AsyncSessionTransaction, *exc: Any) -> None:
        nonlocal pendiente
        if not pendiente:
            await salir(tx, *exc)
            return
        pendiente = False
        if not confirmado:
            await tx.rollback()
        await salir(tx, *exc)
        raise OperationalError(None, None, RuntimeError("respuesta perdida"))

    with monkeypatch.context() as contexto:
        contexto.setattr(clase, "guardar", escrita)
        contexto.setattr(AsyncSessionTransaction, "__aexit__", salida)
        assert await worker.lote(1, 1, asyncio.Event()) == 0
    ev = await fila(factory, resultado.carta_id)
    assert await proyeccion.coleccion.count_documents({"_id": ev.id}) == 1
    if confirmado:
        assert ev.status == "PROCESSED" and await repo.reclamar(1) == []
    else:
        assert ev.status == "PROCESSING"
        await cambiar(factory, ev.id, lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        _, nuevo = componentes(factory, proyeccion.almacen)
        assert await nuevo.lote(1, 1, asyncio.Event()) == 1
    assert await proyeccion.coleccion.count_documents({"_id": ev.id}) == 1


@pytest.mark.usefixtures("cola_vacia")
async def test_reinicio_despues_de_mongo_y_agotamiento(
    mongo: MongoPrueba, factory: SessionFactory, proyeccion: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una cancelación tras Mongo deja lease recuperable y conserva fallos agotados."""
    resultado = await crear_carta(mongo)
    _, worker = componentes(factory, proyeccion.almacen)
    clase = type(proyeccion.almacen)
    guardar = clase.guardar

    async def interrumpir(almacen: Any, carta: Any) -> None:
        await guardar(almacen, carta)
        raise asyncio.CancelledError()

    with monkeypatch.context() as contexto:
        contexto.setattr(clase, "guardar", interrumpir)
        with pytest.raises(asyncio.CancelledError):
            await worker.lote(1, 1, asyncio.Event())
    ev = await fila(factory, resultado.carta_id)
    assert ev.status == "PROCESSING"
    assert await proyeccion.coleccion.count_documents({"_id": ev.id}) == 1
    await cambiar(factory, ev.id, lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
    _, nuevo = componentes(factory, proyeccion.almacen)
    assert await nuevo.lote(1, 1, asyncio.Event()) == 1

    resultado = await crear_carta(mongo)
    repo, _ = componentes(factory, proyeccion.almacen, max_intentos=1)
    [reclamado] = await repo.reclamar(1)
    assert reclamado.id == resultado.carta_id
    await cambiar(factory, reclamado.id, lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert await repo.reclamar(1) == []
    agotado = await fila(factory, reclamado.id)
    assert agotado.status == "FAILED" and agotado.sanitized_error == "intentos_agotados"


@pytest.mark.parametrize("modificacion", ["schema", "payload", "sql", "no_ready", "ajeno"])
@pytest.mark.usefixtures("cola_vacia")
async def test_eventos_incompatibles_o_ajenos(
    mongo: MongoPrueba, factory: SessionFactory, proyeccion: Any, modificacion: str
) -> None:
    """Conserva payload incompatible y excluye eventos de otro consumidor."""
    resultado = await crear_carta(mongo)
    ev = await fila(factory, resultado.carta_id)
    valores: dict[str, Any]
    if modificacion == "schema":
        valores = {"schema_version": 2}
    elif modificacion == "payload":
        valores = {"payload": ev.payload | {"payload": ["incorrecto"]}}
    elif modificacion == "sql":
        valores = {"payload": ev.payload | {"payload": ev.payload["payload"] | {"name": "Otro"}}}
    elif modificacion == "no_ready":
        valores = {}
        async with factory() as sesion, sesion.begin():
            await sesion.execute(
                update(ImagenORM)
                .where(ImagenORM.id == ev.aggregate_id)
                .values(state="RETRY_PENDING")
            )
    else:
        valores = {"event_type": "CardUpdated"}
    if valores:
        await cambiar(factory, ev.id, **valores)
    _, worker = componentes(factory, proyeccion.almacen)
    assert await worker.lote(1, 1, asyncio.Event()) == 0
    nuevo = await fila(factory, ev.id)
    assert nuevo.payload == valores.get("payload", ev.payload)
    if modificacion == "ajeno":
        assert nuevo.status == "PENDING" and nuevo.attempts == 0
    else:
        assert nuevo.status == "FAILED" and nuevo.attempts == 1 and nuevo.sanitized_error
    assert await proyeccion.coleccion.find_one({"_id": ev.id}) is None


async def test_proyeccion_monotona_y_colision(proyeccion: Any) -> None:
    """Dos inserciones, versiones desordenadas y código de otra carta son distinguibles."""
    id_carta = str(uuid4())
    codigo = f"prueba-{id_carta}"
    vieja = dominio.ProyeccionCarta(id_carta, 1, {"id": id_carta, "code": codigo, "name": "Uno"})
    reciente = replace(vieja, version=2, campos=vieja.campos | {"name": "Dos"})
    almacen = proyeccion.almacen
    async with asyncio.timeout(15):
        await asyncio.gather(almacen.guardar(vieja), almacen.guardar(vieja))
    await almacen.guardar(reciente)
    await almacen.guardar(vieja)
    await almacen.guardar(reciente)
    assert await proyeccion.coleccion.find_one({"_id": id_carta}) == reciente.documento()
    assert await proyeccion.coleccion.count_documents({"code": codigo}) == 1
    with pytest.raises(dominio.EventoIncompatible, match="codigo_ocupado_por_otro_id"):
        await almacen.guardar(replace(vieja, id=str(uuid4())))
    with pytest.raises(dominio.EventoIncompatible, match="version_igual_con_datos_distintos"):
        await almacen.guardar(replace(reciente, campos=vieja.campos))
