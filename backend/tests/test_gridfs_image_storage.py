"""Integración GridFS autenticada con base desechable y contraste opcional SQL."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from bson import ObjectId
from gridfs import AsyncGridFSBucket
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import AutoReconnect, OperationFailure
from pymongo.uri_parser import parse_uri
from sqlalchemy import select

from src.database.mongodb.connection import (
    close_mongo_connection,
    get_mongo_client,
    get_mongo_db,
)
from src.modules.catalogo import catalogo_module as catalogo
from src.shared.config import get_settings
from tests.test_card_persistence import ImagenORM, SessionFactory
from tests.test_card_persistence import factory as factory
from tests.test_image_processing import binario_imagen, png_en_limite

errors = catalogo.puertos_imagenes
model = catalogo.dominio_imagenes


@dataclass
class MongoPrueba:
    """Conexión compartida y adaptador sobre el bucket limitado de prueba."""

    db: AsyncDatabase[dict[str, Any]]
    almacen: Any


def oid(referencia: str) -> ObjectId:
    """Traduce la referencia canónica en las consultas de inspección de pruebas."""
    return ObjectId(referencia.removeprefix("gridfs:"))


def imagen_procesada() -> Any:
    """Crea un par legítimo para probar escrituras y recuperación."""
    return catalogo.crear_procesador_imagenes().procesar(binario_imagen())


@pytest_asyncio.fixture(loop_scope="function")
async def mongo(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[MongoPrueba]:
    """Requiere MongoDB 7 aislado y credenciales explícitas de aplicación."""
    url = os.environ.get("MONGO_GRIDFS_TEST_URL")
    if not url:
        pytest.skip("Requiere MONGO_GRIDFS_TEST_URL autenticada de MongoDB aislado")
    destino = parse_uri(url)
    database = destino["database"]
    assert isinstance(database, str) and database.startswith("pokearena_gridfs_test_")
    assert destino["username"] == "media_test" and destino["password"]
    assert all(host == "127.0.0.1" and port != 27017 for host, port in destino["nodelist"])
    monkeypatch.setenv("MONGO_URL", url)
    monkeypatch.setenv("MONGO_DB", database)
    monkeypatch.setenv("MONGO_GRIDFS_BUCKET", "card_assets")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused@localhost/unused")
    get_settings.cache_clear()
    try:
        db = get_mongo_db()
        assert get_mongo_client() is db.client
        assert (await db.command("buildInfo"))["versionArray"][0] == 7
        yield MongoPrueba(db, catalogo.crear_almacen_imagenes())
    finally:
        await close_mongo_connection()
        get_settings.cache_clear()


async def test_gridfs_round_trip_y_borrado_limitado(mongo: MongoPrueba) -> None:
    """Verifica bytes, hash, índices, permisos y eliminación por ID exacto."""
    imagen = catalogo.crear_procesador_imagenes().procesar(png_en_limite())
    refs = mongo.almacen.reservar()
    otras = mongo.almacen.reservar()
    resultado = await mongo.almacen.guardar_par(refs, imagen)
    await mongo.almacen.guardar_par(otras, imagen)
    assert await mongo.almacen.recuperar(refs.original) == imagen.original.datos
    assert await mongo.almacen.recuperar(refs.miniatura) == imagen.miniatura.datos
    assert (
        sha256(await mongo.almacen.recuperar(refs.original)).hexdigest()
        == resultado.original.sha256
    )
    await mongo.almacen.verificar_par(resultado)
    chunks = await mongo.db["card_assets.chunks"].index_information()
    assert chunks["files_id_1_n_1"]["unique"]
    assert (
        await mongo.db["card_assets.chunks"].count_documents({"files_id": oid(refs.original)}) > 1
    )
    assert "filename_1_uploadDate_1" in await mongo.db["card_assets.files"].index_information()
    with pytest.raises(OperationFailure) as exc:
        await mongo.db["cards_projection"].find_one()
    assert exc.value.code == 13
    await mongo.almacen.eliminar(refs.original)
    await mongo.almacen.eliminar(refs.original)
    with pytest.raises(errors.ArchivoNoExiste):
        await mongo.almacen.recuperar(refs.original)
    assert await mongo.almacen.recuperar(refs.miniatura) == imagen.miniatura.datos
    assert await mongo.almacen.recuperar(otras.original) == imagen.original.datos


async def test_gridfs_reintento_tras_resultado_incierto(
    mongo: MongoPrueba,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simula pérdida de confirmación tras persistir miniatura y reutiliza sus IDs."""
    guardar = AsyncGridFSBucket.upload_from_stream_with_id

    async def desconectar(
        bucket: AsyncGridFSBucket,
        file_id: ObjectId,
        nombre: str,
        datos: bytes,
    ) -> None:
        await guardar(bucket, file_id, nombre, datos)
        if nombre == "thumbnail.webp":
            raise AutoReconnect("diagnóstico privado simulado")

    imagen = imagen_procesada()
    refs = mongo.almacen.reservar()
    with monkeypatch.context() as contexto:
        contexto.setattr(AsyncGridFSBucket, "upload_from_stream_with_id", desconectar)
        with pytest.raises(errors.ErrorGuardadoPar) as exc:
            await mongo.almacen.guardar_par(refs, imagen)
    assert exc.value.referencias == refs
    assert exc.value.confirmadas == (refs.original,)
    assert isinstance(exc.value.causa, errors.ErrorAlmacenamiento)
    assert exc.value.causa.reintentable and "privado" not in str(exc.value.causa)
    resultado = await mongo.almacen.guardar_par(refs, imagen)
    assert resultado.referencias == refs
    await mongo.almacen.verificar_par(resultado)
    files = mongo.db["card_assets.files"]
    assert (
        await files.count_documents({"_id": {"$in": [oid(refs.original), oid(refs.miniatura)]}})
        == 2
    )
    # A same-ID request with different bytes is rejected and leaves the old file intact.
    otra_imagen = catalogo.crear_procesador_imagenes().procesar(binario_imagen("JPEG"))
    with pytest.raises(errors.ErrorGuardadoPar) as conflicto:
        await mongo.almacen.guardar_par(refs, otra_imagen)
    assert isinstance(conflicto.value.causa, errors.ContenidoInconsistente)
    assert await mongo.almacen.recuperar(refs.original) == imagen.original.datos


async def test_gridfs_fragmento_huerfano_y_compensacion(
    mongo: MongoPrueba,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identifica un fragmento parcial, comunica fallo de limpieza y permite repetir."""
    guardar = AsyncGridFSBucket.upload_from_stream_with_id
    imagen = imagen_procesada()
    ajenas = mongo.almacen.reservar()
    refs = mongo.almacen.reservar()
    await mongo.almacen.guardar_par(ajenas, imagen)
    chunks = mongo.db["card_assets.chunks"]

    async def interrumpir(
        bucket: AsyncGridFSBucket,
        file_id: ObjectId,
        nombre: str,
        datos: bytes,
    ) -> None:
        if nombre == "thumbnail.webp":
            await chunks.insert_one({"files_id": file_id, "n": 0, "data": datos[:16]})
            raise AutoReconnect("escritura interrumpida")
        await guardar(bucket, file_id, nombre, datos)

    async def fallar_borrado(bucket: AsyncGridFSBucket, file_id: ObjectId) -> None:
        raise AutoReconnect("borrado interrumpido")

    with monkeypatch.context() as contexto:
        contexto.setattr(AsyncGridFSBucket, "upload_from_stream_with_id", interrumpir)
        with pytest.raises(errors.ErrorGuardadoPar) as exc:
            await mongo.almacen.guardar_par(refs, imagen)
        assert exc.value.confirmadas == (refs.original,)
    with pytest.raises(errors.ArchivoNoExiste):
        await mongo.almacen.recuperar(refs.miniatura)
    assert await chunks.count_documents({"files_id": oid(refs.miniatura)}) == 1
    with monkeypatch.context() as contexto:
        contexto.setattr(AsyncGridFSBucket, "delete", fallar_borrado)
        with pytest.raises(errors.ErrorAlmacenamiento) as exc:
            await mongo.almacen.eliminar(refs.miniatura)
        assert exc.value.reintentable
    await mongo.almacen.eliminar(refs.miniatura)
    assert await chunks.count_documents({"files_id": oid(refs.miniatura)}) == 0
    resultado = await mongo.almacen.guardar_par(refs, imagen)
    await mongo.almacen.verificar_par(resultado)
    assert await mongo.almacen.recuperar(ajenas.miniatura) == imagen.miniatura.datos


async def test_gridfs_detecta_corrupcion_y_referencia_invalida(mongo: MongoPrueba) -> None:
    """Falla al recuperar fragmentos faltantes y nunca acepta una ruta como ID."""
    refs = mongo.almacen.reservar()
    resultado = await mongo.almacen.guardar_par(refs, imagen_procesada())
    await mongo.db["card_assets.chunks"].delete_one({"files_id": oid(refs.miniatura), "n": 0})
    with pytest.raises(errors.ContenidoInconsistente):
        await mongo.almacen.verificar_par(resultado)
    with pytest.raises(errors.ContenidoInconsistente):
        await mongo.almacen.recuperar("./uploads/miniatura.webp")


async def test_gridfs_rechaza_longitud_excesiva_antes_de_leer(mongo: MongoPrueba) -> None:
    """Una longitud malformada se rechaza antes de intentar recuperar chunks."""
    referencia = mongo.almacen.reservar().original
    await mongo.db["card_assets.files"].insert_one(
        {
            "_id": oid(referencia),
            "length": 5_000_001,
            "chunkSize": 261120,
            "filename": "test-oversize",
            "uploadDate": datetime.now(UTC),
        }
    )
    with pytest.raises(errors.ContenidoInconsistente, match="Longitud"):
        await mongo.almacen.recuperar(referencia)
    await mongo.almacen.eliminar(referencia)


async def test_gridfs_fallo_del_original_no_reporta_exito(
    mongo: MongoPrueba,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo del driver antes de la primera confirmación detiene el par."""

    async def no_escribir(
        bucket: AsyncGridFSBucket,
        file_id: ObjectId,
        nombre: str,
        datos: bytes,
    ) -> None:
        raise OperationFailure("permiso denegado", code=13)

    refs = mongo.almacen.reservar()
    monkeypatch.setattr(AsyncGridFSBucket, "upload_from_stream_with_id", no_escribir)
    with pytest.raises(errors.ErrorGuardadoPar) as exc:
        await mongo.almacen.guardar_par(refs, imagen_procesada())
    assert exc.value.confirmadas == ()
    assert not exc.value.causa.reintentable


async def test_gridfs_contrasta_metadatos_sql_y_detecta_miniatura_ausente(
    mongo: MongoPrueba,
    factory: SessionFactory,
) -> None:
    """Recorre ORM en revisión 1B.2B y verifica ambos binarios usando datos SQL."""
    refs = mongo.almacen.reservar()
    guardada = await mongo.almacen.guardar_par(refs, imagen_procesada())
    original, mini = guardada.original, guardada.miniatura
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        fila = ImagenORM(
            id=str(uuid4()),
            state="PENDING",
            original_storage_key=refs.original,
            original_sha256=original.sha256,
            image_format=original.formato,
            byte_size=original.tamano,
            width=original.ancho,
            height=original.alto,
            thumbnail_storage_key=refs.miniatura,
            thumbnail_format=mini.formato,
            thumbnail_byte_size=mini.tamano,
            thumbnail_width=mini.ancho,
            thumbnail_height=mini.alto,
            created_at=now,
            updated_at=now,
        )
        session.add(fila)
        await session.flush()
        leida = await session.scalar(
            select(ImagenORM)
            .where(ImagenORM.id == fila.id)
            .execution_options(populate_existing=True)
        )
        assert leida is not None
        sql = model.ImagenAlmacenada(
            model.ReferenciasImagen(leida.original_storage_key, leida.thumbnail_storage_key),
            model.MetadatosImagen(
                model.FormatoImagen(leida.image_format),
                leida.width,
                leida.height,
                leida.byte_size,
                leida.original_sha256,
            ),
            model.MetadatosImagen(
                model.FormatoImagen(leida.thumbnail_format),
                leida.thumbnail_width,
                leida.thumbnail_height,
                leida.thumbnail_byte_size,
            ),
        )
        await mongo.almacen.verificar_par(sql)
        with pytest.raises(errors.ContenidoInconsistente):
            await mongo.almacen.verificar_par(
                replace(sql, original=replace(sql.original, sha256="0" * 64))
            )
        await mongo.almacen.eliminar(refs.miniatura)
        with pytest.raises(errors.ArchivoNoExiste):
            await mongo.almacen.verificar_par(sql)
        assert leida.state == "PENDING"
        await mongo.almacen.guardar_par(refs, imagen_procesada())
        await mongo.almacen.verificar_par(sql)
        # Solo esta prueba verifica que los metadatos íntegros son admisibles en 1B.2B.
        leida.state = "READY"
        await session.flush()
        await session.rollback()
