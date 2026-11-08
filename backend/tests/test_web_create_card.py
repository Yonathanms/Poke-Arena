"""Contrato ASGI, autenticación criptográfica y creación HTTP en motores aislados."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_urlsafe
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text

from src.modules.catalogo import catalogo_module as catalogo
from src.modules.identidad import identidad_module as identidad
from src.shared.config import get_settings
from tests.test_card_persistence import SessionFactory
from tests.test_card_persistence import factory as factory
from tests.test_gridfs_image_storage import MongoPrueba, oid
from tests.test_gridfs_image_storage import mongo as mongo
from tests.test_image_processing import binario_imagen
from tests.test_service_crear_carta import contador, estado

_CARTAS = "/api/v1/content/cards"
_LOGIN = "/api/v1/identity/google/session"
_CLIENT_ID = "local-tests"
_ADMIN = "12345001"
_JUGADOR = "12345002"
_CAMPOS = {
    "name": "Guardiana",
    "cost": "2",
    "power": "-5",
    "card_type": "LUC",
    "rarity": "RARA",
    "ability_code": "HAB-000",
}
_servicio = catalogo.aplicacion_cartas


def _app() -> FastAPI:
    from src.main import crear_app

    return crear_app()


async def _post(
    cliente: AsyncClient,
    clave: str | None,
    *,
    campos: dict[str, str] | None = None,
    imagen: bytes | None = b"imagen",
    token: str | None = None,
) -> Response:
    headers = {}
    if clave is not None:
        headers["Idempotency-Key"] = clave
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return await cliente.post(
        _CARTAS,
        headers=headers,
        data=_CAMPOS if campos is None else campos,
        files={"image": ("carta.png", imagen, "image/png")} if imagen is not None else {},
    )


def _problema(respuesta: Response, status: int, codigo: str) -> None:
    assert respuesta.status_code == status, respuesta.text
    assert respuesta.headers["Content-Type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["status"] == status and cuerpo["code"] == codigo
    assert cuerpo["correlation_id"] == respuesta.headers["X-Correlation-ID"]


@pytest.fixture
def ajuste_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Da configuración explícita sin contactar ninguna base."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused@localhost/unused")
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", _CLIENT_ID)
    monkeypatch.setenv("IDENTITY_LOCAL_ENABLED", "false")
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def web(
    ajuste_local: None, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[AsyncClient, AsyncMock]]:
    """Sustituye dependencias en la app de pruebas con un servicio observable."""
    ejecutar = AsyncMock(
        return_value=_servicio.ResultadoCrearCarta(
            "carta",
            "PKA-LUC-001",
            "operacion",
            "imagen",
        )
    )
    monkeypatch.setattr(
        catalogo, "crear_servicio_crear_carta", lambda: SimpleNamespace(ejecutar=ejecutar)
    )
    app = _app()

    async def admin() -> str:
        return "actor-autenticado"

    app.dependency_overrides[identidad.requerir_administrador] = admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
            yield cliente, ejecutar
    finally:
        get_settings.cache_clear()


async def test_api_delega_y_documenta(web: tuple[AsyncClient, AsyncMock]) -> None:
    """Comprueba ruta histórica, multipart, actor, headers y OpenAPI."""
    cliente, ejecutar = web
    respuesta = await _post(cliente, "clave-valida")
    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id": "carta",
        "code": "PKA-LUC-001",
        "operation_id": "operacion",
        "image_id": "imagen",
        "image_status": "READY",
    }
    assert respuesta.headers["X-Correlation-ID"] == "operacion"
    assert ejecutar.await_args is not None
    actor, peticion = ejecutar.await_args.args
    assert actor.id == "actor-autenticado" and peticion.original == b"imagen"
    assert peticion.datos.costo == 2 and peticion.datos.poder == -5
    assert peticion.clave_idempotencia == "clave-valida"
    doc = (await cliente.get("/openapi.json")).json()
    ruta = doc["paths"][_CARTAS]["post"]
    assert ruta["security"] == [{"PlatformBearerAuth": []}]
    assert ruta["parameters"][0]["name"] == "Idempotency-Key"
    assert ruta["parameters"][0]["required"]
    esquema = ruta["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert esquema["properties"]["image"]["format"] == "binary"
    assert set(esquema["required"]) == _CAMPOS.keys() | {"image"}
    assert "application/problem+json" in ruta["responses"]["422"]["content"]
    assert (await cliente.get("/docs")).status_code == 200


@pytest.mark.parametrize(
    ("clave", "cambios", "imagen", "codigo"),
    [
        (None, {}, b"x", "solicitud_invalida"),
        ("", {}, b"x", "solicitud_invalida"),
        ("x" * 129, {}, b"x", "solicitud_invalida"),
        ("x,y", {}, b"x", "solicitud_invalida"),
        ("clave", {"name": None}, b"x", "solicitud_invalida"),
        ("clave", {"cost": "abc"}, b"x", "solicitud_invalida"),
        ("clave", {"actor_id": "externo"}, b"x", "multipart_invalido"),
        ("clave", {}, None, "multipart_requerido"),
    ],
)
async def test_transporte_invalido_no_invoca(
    web: tuple[AsyncClient, AsyncMock],
    clave: str | None,
    cambios: dict[str, str | None],
    imagen: bytes | None,
    codigo: str,
) -> None:
    """Rechaza campos, credenciales de idempotencia y media type inválidos."""
    cliente, ejecutar = web
    campos = {k: v for k, v in (_CAMPOS | cambios).items() if v is not None}
    respuesta = await _post(cliente, clave, campos=campos, imagen=imagen)
    _problema(respuesta, 415 if imagen is None else 422, codigo)
    ejecutar.assert_not_awaited()


@pytest.mark.parametrize("longitud", [None, "1"])
async def test_limite_de_bytes_real(
    web: tuple[AsyncClient, AsyncMock], longitud: str | None
) -> None:
    """Rechaza un flujo superior al presupuesto con Content-Length ausente o falso."""
    cliente, ejecutar = web
    headers = {"Content-Type": "multipart/form-data; boundary=x", "Idempotency-Key": "clave"}
    if longitud is not None:
        headers["Content-Length"] = longitud

    async def cuerpo() -> AsyncIterator[bytes]:
        yield b'--x\r\nContent-Disposition: form-data; name="image"; filename="x.png"\r\n\r\n'
        for _ in range(6):
            yield b"x" * 1_000_000
        yield b"\r\n--x--\r\n"

    respuesta = await cliente.post(_CARTAS, headers=headers, content=cuerpo())
    _problema(respuesta, 413, "imagen_demasiado_grande")
    ejecutar.assert_not_awaited()


@pytest.mark.parametrize("bytes_archivo", [5_000_000, 5_000_001])
async def test_limite_del_archivo(web: tuple[AsyncClient, AsyncMock], bytes_archivo: int) -> None:
    """El límite incluye exactamente 5 MB decimales de archivo."""
    cliente, ejecutar = web
    respuesta = await _post(cliente, "clave", imagen=b"x" * bytes_archivo)
    if bytes_archivo == 5_000_000:
        assert respuesta.status_code == 201
        assert ejecutar.await_args is not None
        assert len(ejecutar.await_args.args[1].original) == bytes_archivo
    else:
        _problema(respuesta, 413, "imagen_demasiado_grande")
        ejecutar.assert_not_awaited()


@pytest.mark.parametrize(
    ("tipo", "status"),
    [
        ("datos_invalidos", 422),
        ("evolucion_invalida", 422),
        ("imagen_invalida", 422),
        ("habilidad_inexistente", 404),
        ("codigo_agotado", 409),
        ("conflicto_idempotencia", 409),
        ("en_curso", 409),
        ("reserva_incompatible", 409),
        ("resultado_incompatible", 409),
        ("reserva_incierta", 409),
        ("compensacion_pendiente", 409),
        ("imagen_inconsistente", 409),
        ("procesamiento_imagen", 500),
        ("almacenamiento", 503),
        ("transaccion", 503),
        ("commit_incierto", 503),
    ],
)
async def test_traduccion_tipificada(
    web: tuple[AsyncClient, AsyncMock], tipo: str, status: int
) -> None:
    """Traduce toda la taxonomía 1D sin entregar IDs técnicos de error."""
    cliente, ejecutar = web
    ejecutar.side_effect = _servicio.ErrorCreacion(_servicio.TipoErrorCreacion(tipo), "oculto")
    respuesta = await _post(cliente, "clave")
    _problema(respuesta, status, tipo)
    assert "oculto" not in respuesta.text


async def test_error_inesperado_sanitizado(web: tuple[AsyncClient, AsyncMock]) -> None:
    """El controlador evita que los detalles de una excepción lleguen al transporte."""
    cliente, ejecutar = web
    ejecutar.side_effect = RuntimeError("credencial privada")
    respuesta = await _post(cliente, "clave")
    _problema(respuesta, 500, "error_interno")
    assert "credencial privada" not in respuesta.text


async def test_autenticacion_precede_lectura(ajuste_local: None) -> None:
    """Los headers falsos no evitan el Bearer ni hacen leer un cuerpo no autenticado."""

    async def cuerpo() -> AsyncIterator[bytes]:
        pytest.fail("La API leyó el cuerpo antes de autenticar")
        yield b""

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as cliente:
        respuesta = await cliente.post(
            _CARTAS, content=cuerpo(), headers={"X-Admin": "true", "X-Actor-ID": "falso"}
        )
    _problema(respuesta, 401, "credencial_invalida")
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


async def test_multipart_sin_archivo_y_frontera_incompleta(
    web: tuple[AsyncClient, AsyncMock],
) -> None:
    """Rechaza un formulario multipart sin archivo y un archivo truncado."""
    cliente, ejecutar = web
    respuesta = await cliente.post(
        _CARTAS,
        headers={"Idempotency-Key": "clave"},
        files=[(k, (None, v)) for k, v in _CAMPOS.items()],
    )
    _problema(respuesta, 422, "imagen_requerida")
    respuesta = await cliente.post(
        _CARTAS,
        headers={
            "Idempotency-Key": "clave",
            "Content-Type": "multipart/form-data; boundary=x",
        },
        content=b'--x\r\nContent-Disposition: form-data; name="image"; filename="x"\r\n\r\nx',
    )
    _problema(respuesta, 422, "multipart_invalido")
    ejecutar.assert_not_awaited()


async def test_login_cuerpo_acotado_y_configuracion_ausente(
    ajuste_local: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El login público limita JSON y falla cerrado cuando falta el client ID."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    get_settings.cache_clear()
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as cliente:
        _problema(
            await cliente.post(_LOGIN, json={"google_id_token": "x" * 20_000}),
            413,
            "cuerpo_demasiado_grande",
        )
        _problema(
            await cliente.post(_LOGIN, json={"google_id_token": "x"}),
            503,
            "identidad_no_disponible",
        )
    get_settings.cache_clear()


async def test_cors_solo_origenes_aprobados(
    ajuste_local: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Permite el preflight configurado y rechaza un origen ajeno."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://arena.example")
    get_settings.cache_clear()
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as cliente:
        headers = {
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Idempotency-Key",
        }
        permitido = await cliente.options(
            _CARTAS, headers=headers | {"Origin": "https://arena.example"}
        )
        ajeno = await cliente.options(_CARTAS, headers=headers | {"Origin": "https://otro.example"})
        assert permitido.headers["Access-Control-Allow-Origin"] == "https://arena.example"
        assert "Access-Control-Allow-Credentials" not in permitido.headers
        assert ajeno.status_code == 400 and "Access-Control-Allow-Origin" not in ajeno.headers
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def clave_rsa() -> rsa.RSAPrivateKey:
    """Clave de pruebas generada en memoria, sin secretos externos."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token_google(clave: rsa.RSAPrivateKey, **cambios: Any) -> str:
    ahora = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": "https://accounts.google.com",
        "sub": _ADMIN,
        "exp": ahora + 60,
        "iat": ahora,
        "aud": _CLIENT_ID,
    }
    return jwt.encode(claims | cambios, clave, algorithm="RS256", headers={"kid": "local"})


def _claves_locales(monkeypatch: pytest.MonkeyPatch, clave: rsa.RSAPrivateKey) -> None:
    datos = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(clave.public_key()))
    firma = jwt.PyJWK.from_dict(datos | {"kid": "local", "alg": "RS256"})
    monkeypatch.setattr(
        identidad._google, "_claves", lambda: SimpleNamespace(get_signing_keys=lambda: [firma])
    )


@pytest.mark.parametrize(
    "cambios",
    [{"aud": "otro"}, {"iss": "otro"}, {"exp": 1}, {"sub": ""}, {"azp": "otro"}, {"iat": True}],
)
async def test_google_rechaza_claims_firmados(
    monkeypatch: pytest.MonkeyPatch, clave_rsa: rsa.RSAPrivateKey, cambios: dict[str, Any]
) -> None:
    """Una firma válida no sustituye audiencia, emisor, vigencia ni subject."""
    _claves_locales(monkeypatch, clave_rsa)
    with pytest.raises(identidad._google.IdentidadInvalida):
        await identidad._google.verificar_google(_token_google(clave_rsa, **cambios), _CLIENT_ID)


async def test_google_rechaza_firma_y_algoritmo(
    monkeypatch: pytest.MonkeyPatch, clave_rsa: rsa.RSAPrivateKey
) -> None:
    """Acepta una credencial válida y rechaza firma ajena y algoritmo simétrico."""
    _claves_locales(monkeypatch, clave_rsa)
    correcto = _token_google(clave_rsa)
    assert await identidad._google.verificar_google(correcto, _CLIENT_ID) == _ADMIN
    otra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    simetrico = jwt.encode({"sub": _ADMIN}, b"x" * 32, algorithm="HS256", headers={"kid": "local"})
    for token in (_token_google(otra), simetrico, "token-no-jwt"):
        with pytest.raises(identidad._google.IdentidadInvalida):
            await identidad._google.verificar_google(token, _CLIENT_ID)


async def test_http_real_con_seguridad_y_ambos_motores(
    mongo: MongoPrueba,
    factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
    clave_rsa: rsa.RSAPrivateKey,
) -> None:
    """Ejecuta OIDC, autorización, concurrencia, replay y almacenamiento reales."""
    _claves_locales(monkeypatch, clave_rsa)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", _CLIENT_ID)
    monkeypatch.setenv("PLATFORM_ADMIN_GOOGLE_SUBJECTS", _ADMIN)
    get_settings.cache_clear()
    antes = await contador(factory)
    original = binario_imagen()
    clave = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as cliente:
        login = await cliente.post(_LOGIN, json={"google_id_token": _token_google(clave_rsa)})
        assert login.status_code == 201, login.text
        assert login.headers["Cache-Control"] == "no-store"
        admin = login.json()
        assert admin["role"] == "PLATFORM_ADMIN"
        no_admin = (
            await cliente.post(
                _LOGIN, json={"google_id_token": _token_google(clave_rsa, sub=_JUGADOR)}
            )
        ).json()
        _problema(
            await _post(cliente, clave, token=no_admin["access_token"]), 403, "permiso_denegado"
        )
        _problema(
            await _post(cliente, clave, token=_token_google(clave_rsa)), 401, "credencial_invalida"
        )
        token = admin["access_token"]
        _problema(await _post(cliente, clave, token=token_urlsafe(32)), 401, "credencial_invalida")
        for campo, valor in (("cost", "11"), ("power", "21"), ("card_type", "X"), ("rarity", "X")):
            respuesta = await _post(cliente, clave, campos=_CAMPOS | {campo: valor}, token=token)
            _problema(respuesta, 422, "datos_invalidos")
        _problema(
            await _post(cliente, clave, imagen=b"no es imagen", token=token), 422, "imagen_invalida"
        )
        _problema(
            await _post(
                cliente,
                clave,
                campos=_CAMPOS | {"ability_code": "HAB-999"},
                imagen=original,
                token=token,
            ),
            404,
            "habilidad_inexistente",
        )

        otra_clave = str(uuid4())
        async with asyncio.timeout(15):
            primera, segunda = await asyncio.gather(
                _post(cliente, clave, imagen=original, token=token),
                _post(cliente, otra_clave, imagen=original, token=token),
            )
        assert primera.status_code == segunda.status_code == 201
        assert {r.json()["code"] for r in (primera, segunda)} == {
            f"PKA-LUC-{antes + 1:03d}",
            f"PKA-LUC-{antes + 2:03d}",
        }
        replay = await _post(cliente, clave, imagen=original, token=token)
        assert replay.status_code == 201 and replay.json() == primera.json()
        _problema(
            await _post(
                cliente, clave, imagen=original, campos=_CAMPOS | {"cost": "3"}, token=token
            ),
            409,
            "conflicto_idempotencia",
        )

        async with factory() as session, session.begin():
            huella = sha256(token.encode()).hexdigest()
            assert (
                await session.scalar(
                    text("SELECT user_id FROM identity_sessions WHERE token_hash=:huella"),
                    {"huella": huella},
                )
                == admin["user_id"]
            )
            await session.execute(
                text("UPDATE identity_sessions SET expires_at=now() WHERE token_hash=:huella"),
                {"huella": huella},
            )
        _problema(
            await _post(cliente, clave, imagen=original, token=token), 401, "credencial_invalida"
        )
        async with factory() as session, session.begin():
            await session.execute(
                text("""
                    UPDATE identity_sessions
                    SET expires_at=now() + interval '10 minutes', revoked_at=now()
                    WHERE token_hash=:huella
                """),
                {"huella": huella},
            )
        _problema(
            await _post(cliente, clave, imagen=original, token=token), 401, "credencial_invalida"
        )
    assert await contador(factory) == antes + 2
    for llave, respuesta in ((clave, primera), (otra_clave, segunda)):
        filas = await estado(
            factory, SimpleNamespace(id=admin["user_id"]), SimpleNamespace(clave_idempotencia=llave)
        )
        assert filas.carta.id == respuesta.json()["id"]
        assert filas.evento is not None and filas.evento.aggregate_id == filas.carta.id
        assert filas.imagen.state == "READY"
        refs = [oid(filas.imagen.original_storage_key), oid(filas.imagen.thumbnail_storage_key)]
        assert await mongo.db["card_assets.files"].count_documents({"_id": {"$in": refs}}) == 2
        assert await mongo.almacen.recuperar(filas.imagen.original_storage_key) == original
