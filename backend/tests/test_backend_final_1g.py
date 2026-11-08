"""Aceptación de 1G por HTTP loopback y bases autenticadas desechables."""

import asyncio
import json
import os
import socket
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient, HTTPError
from pymongo import AsyncMongoClient
from pymongo.uri_parser import parse_uri
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from src.modules.identidad import identidad_module
from src.shared.config import Settings
from tests.test_card_persistence import BACKEND
from tests.test_image_processing import binario_imagen
from tests.test_web_create_card import _post, _problema

_LOGIN = "/api/v1/identity/local/session"
_REVOCAR = "/api/v1/identity/session"
_HABILIDADES = "/api/v1/content/abilities"


def test_config_local_exige_opt_in_aislado() -> None:
    """Falla cerrado en producción y en la base original."""
    db = "postgresql+asyncpg://unused@localhost/pokearena_alembic_1g_demo"
    mongo = "mongodb://unused@localhost/pokearena_gridfs_test_demo"
    assert not Settings(_env_file=None, DATABASE_URL=db, MONGO_URL=mongo).IDENTITY_LOCAL_ENABLED
    with pytest.raises(ValueError, match="destino PostgreSQL aislado"):
        Settings(
            _env_file=None,
            DATABASE_URL=db,
            MONGO_URL=mongo,
            ENVIRONMENT="production",
            IDENTITY_LOCAL_ENABLED=True,
        )
    with pytest.raises(ValueError, match="destino PostgreSQL aislado"):
        Settings(
            _env_file=None,
            DATABASE_URL=db.replace("pokearena_alembic_1g_demo", "pokearena_db"),
            MONGO_URL=mongo,
            ENVIRONMENT="test",
            IDENTITY_LOCAL_ENABLED=True,
        )


def test_hash_local_sal_y_validacion() -> None:
    """El secreto aleatorio se verifica y la sal cambia en cada aprovisionamiento."""
    clave = token_urlsafe(24)
    modulo = identidad_module._sql
    primero, segundo = modulo.crear_hash(clave), modulo.crear_hash(clave)
    assert primero != segundo and clave not in primero
    assert modulo.verificar_hash(clave, primero)
    assert not modulo.verificar_hash(token_urlsafe(24), primero)
    with pytest.raises(ValueError):
        modulo.crear_hash("corta")


async def _proceso(
    env: dict[str, str],
    *args: str,
    entrada: bytes | None = None,
    retorno: int = 0,
) -> None:
    proceso = await asyncio.create_subprocess_exec(
        sys.executable,
        *args,
        cwd=BACKEND,
        env=env,
        stdin=asyncio.subprocess.PIPE if entrada is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        salida, error = await asyncio.wait_for(proceso.communicate(entrada), 35)
    finally:
        if proceso.returncode is None:
            proceso.kill()
            await proceso.wait()
    if proceso.returncode != retorno:
        mensaje = (salida + error).decode(errors="replace")
        for variable in ("DATABASE_URL", "MONGO_URL", "MIGRATION_DATABASE_URL"):
            if env.get(variable):
                mensaje = mensaje.replace(env[variable], "<URL privada>")
        pytest.fail(mensaje)


@asynccontextmanager
async def _api(env: dict[str, str]) -> AsyncIterator[AsyncClient]:
    """Arranca Uvicorn sobre un socket loopback exclusivo y lo cierra al salir."""
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen()
        puerto = servidor.getsockname()[1]
        fd = servidor.fileno()
        proceso = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "uvicorn",
            "src.main:app",
            "--fd",
            str(fd),
            "--no-access-log",
            cwd=BACKEND,
            env=env,
            pass_fds=(fd,),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    try:
        async with AsyncClient(base_url=f"http://127.0.0.1:{puerto}", timeout=6) as cliente:
            async with asyncio.timeout(15):
                while True:
                    assert proceso.returncode is None, "Uvicorn terminó antes de estar listo"
                    try:
                        respuesta = await cliente.get("/openapi.json", timeout=0.4)
                        if respuesta.status_code == 200:
                            break
                    except HTTPError:
                        pass
                    await asyncio.sleep(0.05)
            yield cliente
    finally:
        if proceso.returncode is None:
            proceso.terminate()
            try:
                await asyncio.wait_for(proceso.wait(), 10)
            except TimeoutError:
                proceso.kill()
                await proceso.wait()


def _destinos() -> tuple[dict[str, str], str]:
    claves = {
        "DATABASE_URL": "IDENTITY_LOCAL_TEST_DATABASE_URL",
        "MONGO_URL": "IDENTITY_LOCAL_TEST_MONGO_URL",
        "MIGRATION_DATABASE_URL": "IDENTITY_LOCAL_TEST_MIGRATION_URL",
        "PROJECTION": "IDENTITY_LOCAL_TEST_PROJECTION_URL",
    }
    if not all(os.environ.get(k) for k in claves.values()):
        pytest.skip("Requiere los destinos dedicados de aceptación 1G")
    urls = {k: os.environ[v] for k, v in claves.items()}
    pg = make_url(urls["DATABASE_URL"])
    migrador = make_url(urls["MIGRATION_DATABASE_URL"])
    assert pg.host == migrador.host == "127.0.0.1" and pg.port == migrador.port != 5432
    assert pg.database == migrador.database == "pokearena_alembic_1g_master"
    assert pg.username == "orm_media_test" and migrador.username == "pokearena_migrator"
    proyeccion = urls.pop("PROJECTION")
    medios, salida = parse_uri(urls["MONGO_URL"]), parse_uri(proyeccion)
    base = medios["database"]
    assert isinstance(base, str) and base.startswith("pokearena_gridfs_test_")
    assert salida["database"] == base and medios["nodelist"] == salida["nodelist"]
    assert medios["username"] == "media_test" and salida["username"] == "projection_test"
    assert all(h == "127.0.0.1" and p != 27017 for h, p in medios["nodelist"])
    return os.environ | urls | {
        "MONGO_DB": base,
        "MONGO_GRIDFS_BUCKET": "card_assets",
        "ENVIRONMENT": "test",
        "IDENTITY_LOCAL_ENABLED": "true",
        "GOOGLE_OAUTH_CLIENT_ID": "",
        "DEBUG": "false",
        "ALLOWED_ORIGINS": "http://localhost:5173",
    }, proyeccion


async def test_administrador_http_carta_gridfs_outbox_y_revocacion() -> None:
    """Verifica credencial, sesiones, replay y publicación por procesos reales."""
    env, proyeccion = _destinos()
    engine = create_async_engine(env["DATABASE_URL"], hide_parameters=True)
    clave = token_urlsafe(28)
    usuario = "maestro-pruebas"
    provisionar = (
        "import asyncio, json, sys; "
        "from src.modules.identidad.identidad_module import provisionar_administrador; "
        "asyncio.run(provisionar_administrador(*json.load(sys.stdin)))"
    )

    async def sql(consulta: str, **parametros: Any) -> Any:
        async with engine.begin() as conn:
            resultado = await conn.execute(text(consulta), parametros)
            return resultado.mappings().one_or_none() if resultado.returns_rows else None

    try:
        revision = await sql("SELECT version_num FROM alembic_version")
        assert revision == {"version_num": "1g_local_master_admin"}
        await _proceso(env, "-c", provisionar, entrada=json.dumps([usuario, clave]).encode())
        await _proceso(
            env, "-c", provisionar, entrada=json.dumps([usuario, token_urlsafe(28)]).encode()
        )
        maestro = await sql("""
            SELECT id, local_password_hash, local_failed_attempts
            FROM identity_users WHERE provider='LOCAL'
        """)
        assert maestro and clave not in maestro["local_password_hash"]
        assert maestro["local_failed_attempts"] == 0

        legado = token_urlsafe(32)
        await sql(
            """
            INSERT INTO identity_sessions (id, user_id, token_hash, expires_at)
            SELECT :id, id, :hash, now() + interval '10 minutes'
            FROM identity_users WHERE provider='TEST' AND provider_subject='preexistente-test'
        """,
            id=str(uuid4()),
            hash=sha256(legado.encode()).hexdigest(),
        )
        async with _api(env | {"IDENTITY_LOCAL_ENABLED": "false"}) as deshabilitada:
            _problema(await deshabilitada.post(_LOGIN, json={}), 404, "http_error")

        async with _api(env) as cliente:
            _problema(
                await cliente.get(_HABILIDADES, headers={"Authorization": f"Bearer {legado}"}),
                401,
                "credencial_invalida",
            )
            _problema(await cliente.post(_LOGIN, json={}), 422, "solicitud_invalida")
            for intento in range(5):
                rechazo = await cliente.post(
                    _LOGIN,
                    json={
                        "username": usuario if intento % 2 else "desconocido",
                        "password": token_urlsafe(28),
                    },
                )
                _problema(rechazo, 401, "credencial_invalida")
                assert usuario not in rechazo.text

        async with _api(env) as cliente:
            bloqueado = await cliente.post(_LOGIN, json={"username": usuario, "password": clave})
            _problema(bloqueado, 429, "intentos_limitados")
            assert int(bloqueado.headers["Retry-After"]) > 0
            await sql(
                """
                UPDATE identity_users SET local_blocked_until=now()-interval '1 second'
                WHERE id=:id
            """,
                id=maestro["id"],
            )
            login = await cliente.post(_LOGIN, json={"username": usuario, "password": clave})
            assert login.status_code == 201 and login.headers["Cache-Control"] == "no-store"
            sesion = login.json()
            token = sesion["access_token"]
            huella = sha256(token.encode()).hexdigest()
            assert sesion["user_id"] == maestro["id"] and sesion["role"] == "PLATFORM_ADMIN"
            assert await sql(
                """
                SELECT token_hash FROM identity_sessions WHERE user_id=:id AND token_hash=:hash
            """,
                id=maestro["id"],
                hash=huella,
            ) == {"token_hash": huella}
            headers = {"Authorization": f"Bearer {token}"}
            _problema(await cliente.get(_HABILIDADES), 401, "credencial_invalida")
            opciones = await cliente.get(_HABILIDADES, headers=headers)
            assert opciones.status_code == 200
            assert {"code": "HAB-000", "name": "Sin Habilidad"} in opciones.json()

            original = binario_imagen()
            llave = str(uuid4())
            respuesta = await _post(cliente, llave, imagen=original, token=token)
            assert respuesta.status_code == 201, respuesta.text
            carta = respuesta.json()
            repetida = await _post(cliente, llave, imagen=original, token=token)
            assert repetida.status_code == 201 and repetida.json() == carta
            assert carta["image_status"] == "READY"
            persistida = await sql(
                """
                SELECT c.code, c.version, h.code AS habilidad, i.state,
                       i.original_storage_key, i.thumbnail_storage_key, i.original_sha256,
                       i.thumbnail_width, i.thumbnail_height, o.status, idem.actor_id, t.last_value
                FROM catalog_cards c JOIN catalog_abilities h ON h.id=c.ability_id
                JOIN catalog_card_images i ON i.id=c.image_id
                JOIN catalog_card_code_counters t ON t.card_type=c.card_type
                JOIN shared_outbox o ON o.aggregate_id=c.id AND o.event_type='CardCreated'
                JOIN shared_idempotency_records idem ON idem.resource_id=c.id
                WHERE c.id=:id
            """,
                id=carta["id"],
            )
            assert persistida and persistida["status"] == "PENDING"
            assert persistida["actor_id"] == maestro["id"]
            assert persistida["code"] == carta["code"] and persistida["last_value"] == 1
            assert persistida["state"] == "READY" and persistida["habilidad"] == "HAB-000"
            assert persistida["original_sha256"] == sha256(original).hexdigest()
            assert (persistida["thumbnail_width"], persistida["thumbnail_height"]) == (200, 280)
            async with AsyncMongoClient[dict[str, Any]](env["MONGO_URL"]) as medios:
                from bson import ObjectId
                from gridfs import AsyncGridFSBucket

                bucket = AsyncGridFSBucket(medios[env["MONGO_DB"]], bucket_name="card_assets")
                for campo in ("original_storage_key", "thumbnail_storage_key"):
                    oid = ObjectId(persistida[campo].removeprefix("gridfs:"))
                    async with await bucket.open_download_stream(oid) as archivo:
                        datos = await archivo.read()
                        if campo == "original_storage_key":
                            assert datos == original
                        else:
                            assert datos[:4] == b"RIFF" and datos[8:12] == b"WEBP"

            async with AsyncMongoClient[dict[str, Any]](proyeccion) as mongo:
                coleccion = mongo[env["MONGO_DB"]]["cards_projection"]
                assert await coleccion.find_one({"_id": carta["id"]}) is None
                await _proceso(
                    env | {"MONGO_URL": proyeccion}, "-m", "src.database.outbox_worker", "--once"
                )
                documento = await coleccion.find_one({"_id": carta["id"]})
                assert documento and documento["aggregate_version"] == persistida["version"]
                assert documento["code"] == carta["code"]
                assert documento["image_status"] == "READY"
                assert await coleccion.count_documents({"code": carta["code"]}) == 1
            assert await sql(
                "SELECT status FROM shared_outbox WHERE aggregate_id=:id", id=carta["id"]
            ) == {"status": "PROCESSED"}

            await sql("UPDATE identity_users SET role='PLAYER' WHERE id=:id", id=maestro["id"])
            _problema(
                await _post(cliente, llave, imagen=original, token=token), 403, "permiso_denegado"
            )
            await sql(
                "UPDATE identity_users SET role='PLATFORM_ADMIN' WHERE id=:id", id=maestro["id"]
            )
            await sql(
                "UPDATE identity_sessions SET expires_at=now() WHERE token_hash=:hash", hash=huella
            )
            _problema(
                await _post(cliente, llave, imagen=original, token=token),
                401,
                "credencial_invalida",
            )
            nuevo = await cliente.post(_LOGIN, json={"username": usuario, "password": clave})
            assert nuevo.status_code == 201
            token = nuevo.json()["access_token"]
            assert (
                await cliente.delete(
                    _REVOCAR,
                    headers={"Authorization": f"Bearer {token}"},
                )
            ).status_code == 204
            _problema(
                await _post(cliente, llave, imagen=original, token=token),
                401,
                "credencial_invalida",
            )
        await _proceso(
            env,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "downgrade",
            "1b2b_card_image_integrity",
            retorno=1,
        )
        assert await sql("SELECT version_num FROM alembic_version") == revision
    finally:
        await engine.dispose()
