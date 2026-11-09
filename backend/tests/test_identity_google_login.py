"""Pruebas de aceptación para el inicio de sesión OIDC con Google y roles de plataforma."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jwt import PyJWKClientConnectionError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.database.postgresql import connection
from src.main import crear_app
from src.modules.identidad import identidad_module as identidad
from src.modules.identidad.identidad_module import Principal
from src.shared.config import get_settings

_CLIENT_ID = "pokearena-test-client"
_ADMIN_SUB = "google-admin-sub-100"
_ADMIN_EMAIL = "admin.pokearena@test.com"
_PLAYER_SUB = "google-player-sub-200"
_PLAYER_EMAIL = "player.pokearena@test.com"
_LOGIN_STD = "/api/v1/identity/login/google"
_LOGIN_HISTORICO = "/api/v1/identity/google/session"
_LOGOUT = "/api/v1/identity/session"


@pytest.fixture(scope="module")
def clave_rsa() -> rsa.RSAPrivateKey:
    """Clave criptográfica de pruebas generada en memoria."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def motor_aislado() -> AsyncIterator[None]:
    """Sustituye el motor con NullPool durante este módulo para evitar fugas entre loops."""
    viejo_engine = connection.engine
    viejo_factory = connection.AsyncSessionLocal

    nuevo_engine = create_async_engine(
        get_settings().DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    nuevo_factory = async_sessionmaker(
        bind=nuevo_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    connection.engine = nuevo_engine
    connection.AsyncSessionLocal = nuevo_factory
    connection.write_engine = nuevo_engine
    connection.AsyncWriteSessionLocal = nuevo_factory
    try:
        yield
    finally:
        await nuevo_engine.dispose()
        connection.engine = viejo_engine
        connection.AsyncSessionLocal = viejo_factory
        connection.write_engine = viejo_engine
        connection.AsyncWriteSessionLocal = viejo_factory


@pytest_asyncio.fixture(autouse=True)
async def limpiar_datos_prueba() -> None:
    """Limpia usuarios, perfiles y sesiones creados antes de cada prueba."""
    async with connection.AsyncSessionLocal() as session, session.begin():
        ids = (
            await session.scalars(
                text("""
                    SELECT id FROM identity_users
                    WHERE provider = 'GOOGLE'
                      AND (
                          provider_subject LIKE 'sub-%'
                          OR provider_subject LIKE 'guard-%'
                          OR provider_subject = :admin_sub
                      )
                """),
                {"admin_sub": _ADMIN_SUB},
            )
        ).all()
        if ids:
            await session.execute(
                text("DELETE FROM identity_sessions WHERE user_id = ANY(:ids)"),
                {"ids": list(ids)},
            )
            await session.execute(
                text("DELETE FROM player_profiles WHERE user_id = ANY(:ids)"),
                {"ids": list(ids)},
            )
            await session.execute(
                text("DELETE FROM identity_users WHERE id = ANY(:ids)"),
                {"ids": list(ids)},
            )


@pytest.fixture
def db() -> async_sessionmaker[AsyncSession]:
    """Provee la fábrica oficial de sesiones de la base de datos de pruebas."""
    return connection.AsyncSessionLocal


def _token_google(
    clave: rsa.RSAPrivateKey,
    sub: str = _PLAYER_SUB,
    email: str | None = _PLAYER_EMAIL,
    client_id: str = _CLIENT_ID,
    **cambios: Any,
) -> str:
    """Genera un Google ID token válido firmado con RS256."""
    ahora = int(datetime.now(UTC).timestamp())
    claims: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "sub": sub,
        "aud": client_id,
        "azp": client_id,
        "exp": ahora + 300,
        "iat": ahora,
    }
    if email is not None:
        claims["email"] = email
        claims["email_verified"] = True
    claims.update(cambios)
    return jwt.encode(claims, clave, algorithm="RS256", headers={"kid": "test-kid"})


def _simular_jwks(monkeypatch: pytest.MonkeyPatch, clave: rsa.RSAPrivateKey) -> None:
    """Configura el JWKS mockeado para que verificar_google use la clave de prueba."""
    datos = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(clave.public_key()))
    firma = jwt.PyJWK.from_dict(datos | {"kid": "test-kid", "alg": "RS256"})
    monkeypatch.setattr(
        identidad._google, "_claves", lambda: SimpleNamespace(get_signing_keys=lambda: [firma])
    )


def _configurar_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Establece variables de entorno seguras para los tests."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", _CLIENT_ID)
    monkeypatch.setenv("PLATFORM_ADMIN_GOOGLE_SUBJECTS", _ADMIN_SUB)
    monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", _ADMIN_EMAIL)
    get_settings.cache_clear()


def _crear_app_con_rutas_protegidas() -> FastAPI:
    """Instancia la app agregando rutas de prueba para verificar guards."""
    app = crear_app()

    @app.get("/api/v1/test/admin-only")
    async def ruta_admin(
        user_id: str = Depends(identidad.requerir_administrador),
    ) -> dict[str, str]:
        return {"admin_id": user_id}

    @app.get("/api/v1/test/player-or-admin")
    async def ruta_jugador(
        principal: Principal = Depends(identidad.requerir_jugador),
    ) -> dict[str, Any]:
        return {"user_id": principal.id, "rol": principal.rol, "email": principal.email}

    return app


async def test_login_nuevo_jugador_crea_usuario_y_perfil(
    db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    clave_rsa: rsa.RSAPrivateKey,
) -> None:
    """Verifica que el primer login cree usuario en identity_users y perfil en player_profiles."""
    _simular_jwks(monkeypatch, clave_rsa)
    _configurar_entorno(monkeypatch)

    app = _crear_app_con_rutas_protegidas()
    token_jwt = _token_google(clave_rsa, sub="sub-nuevo-1", email="nuevo1@test.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Probamos con id_token en el endpoint estándar (200 OK)
        resp = await cliente.post(_LOGIN_STD, json={"id_token": token_jwt})
        assert resp.status_code == 200, resp.text
        assert resp.headers["Cache-Control"] == "no-store"
        datos = resp.json()

        assert datos["is_new_user"] is True
        assert datos["role"] == "PLAYER"
        assert datos["email"] == "nuevo1@test.com"
        assert datos["token_type"] == "Bearer"
        assert isinstance(datos["access_token"], str) and len(datos["access_token"]) == 43
        user_id = datos["user_id"]

        # Consulta al nuevo endpoint de perfil /identity/me
        me_resp = await cliente.get(
            "/api/v1/identity/me",
            headers={"Authorization": f"Bearer {datos['access_token']}"},
        )
        assert me_resp.status_code == 200
        me = me_resp.json()
        assert me["user_id"] == user_id
        assert me["role"] == "PLAYER"
        assert me["email"] == "nuevo1@test.com"
        assert me["elo"] == 0
        assert me["cubes"] == 0
        assert me["has_received_initial_collection"] is False

    # Verificación directa en base de datos
    async with db() as session:
        u = (
            await session.execute(
                text(
                    "SELECT provider, provider_subject, email, role "
                    "FROM identity_users WHERE id = :id"
                ),
                {"id": user_id},
            )
        ).one()
        assert u.provider == "GOOGLE"
        assert u.provider_subject == "sub-nuevo-1"
        assert u.email == "nuevo1@test.com"
        assert u.role == "PLAYER"

        p = (
            await session.execute(
                text(
                    "SELECT elo, cubes, has_received_initial_collection "
                    "FROM player_profiles WHERE user_id = :id"
                ),
                {"id": user_id},
            )
        ).one()
        assert p.elo == 0
        assert p.cubes == 0
        assert p.has_received_initial_collection is False

        # Sesión activa registrada
        huella = sha256(datos["access_token"].encode()).hexdigest()
        s = (
            await session.execute(
                text("SELECT token_hash, revoked_at FROM identity_sessions WHERE user_id = :id"),
                {"id": user_id},
            )
        ).one()
        assert s.token_hash == huella
        assert s.revoked_at is None


async def test_relogin_jugador_existente_es_idempotente(
    db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    clave_rsa: rsa.RSAPrivateKey,
) -> None:
    """Verifica que un login posterior del mismo usuario marque is_new_user=False sin duplicar."""
    _simular_jwks(monkeypatch, clave_rsa)
    _configurar_entorno(monkeypatch)

    app = _crear_app_con_rutas_protegidas()
    token_jwt = _token_google(clave_rsa, sub="sub-existente-2", email="existente2@test.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Primer login
        r1 = await cliente.post(_LOGIN_HISTORICO, json={"google_id_token": token_jwt})
        assert r1.status_code == 201
        d1 = r1.json()
        assert d1["is_new_user"] is True
        user_id = d1["user_id"]

        # Segundo login con mismo subject pero endpoint estándar
        r2 = await cliente.post(_LOGIN_STD, json={"id_token": token_jwt})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["is_new_user"] is False
        assert d2["user_id"] == user_id
        assert d2["role"] == "PLAYER"
        assert d2["email"] == "existente2@test.com"
        # Debe recibir un token nuevo y fresco
        assert d2["access_token"] != d1["access_token"]

    # Verificar que no existen registros duplicados
    async with db() as session:
        cant_usuarios = await session.scalar(
            text("SELECT count(*) FROM identity_users WHERE provider_subject = 'sub-existente-2'")
        )
        assert cant_usuarios == 1

        cant_perfiles = await session.scalar(
            text("SELECT count(*) FROM player_profiles WHERE user_id = :id"),
            {"id": user_id},
        )
        assert cant_perfiles == 1


async def test_login_administrador_por_email_y_subject(
    db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    clave_rsa: rsa.RSAPrivateKey,
) -> None:
    """Comprueba que correos o subjects en allowlist obtienen PLATFORM_ADMIN y perfil de jugador."""
    _simular_jwks(monkeypatch, clave_rsa)
    _configurar_entorno(monkeypatch)

    app = _crear_app_con_rutas_protegidas()

    # Admin por coincidencia de email (en mayúsculas/minúsculas)
    token_admin_email = _token_google(
        clave_rsa, sub="sub-otro-admin", email=_ADMIN_EMAIL.upper()
    )
    # Admin por coincidencia de subject
    token_admin_sub = _token_google(
        clave_rsa, sub=_ADMIN_SUB, email="otro_correo@test.com"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        r_email = await cliente.post(_LOGIN_STD, json={"id_token": token_admin_email})
        assert r_email.status_code == 200
        d_email = r_email.json()
        assert d_email["role"] == "PLATFORM_ADMIN"

        r_sub = await cliente.post(_LOGIN_STD, json={"id_token": token_admin_sub})
        assert r_sub.status_code == 200
        d_sub = r_sub.json()
        assert d_sub["role"] == "PLATFORM_ADMIN"

    # Verificar que el admin también tiene fila en player_profiles
    async with db() as session:
        perfil_admin = await session.scalar(
            text("SELECT count(*) FROM player_profiles WHERE user_id = :id"),
            {"id": d_email["user_id"]},
        )
        assert perfil_admin == 1


async def test_guards_autorizacion_y_revocacion(
    monkeypatch: pytest.MonkeyPatch,
    clave_rsa: rsa.RSAPrivateKey,
) -> None:
    """Verifica que requerir_administrador y requerir_jugador protejan según rol y revocación."""
    _simular_jwks(monkeypatch, clave_rsa)
    _configurar_entorno(monkeypatch)

    app = _crear_app_con_rutas_protegidas()
    token_player = _token_google(clave_rsa, sub="guard-player-sub", email="player.guard@test.com")
    token_admin = _token_google(clave_rsa, sub=_ADMIN_SUB, email="admin.guard@test.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        login_p = (await cliente.post(_LOGIN_STD, json={"id_token": token_player})).json()
        login_a = (await cliente.post(_LOGIN_STD, json={"id_token": token_admin})).json()

        bearer_p = {"Authorization": f"Bearer {login_p['access_token']}"}
        bearer_a = {"Authorization": f"Bearer {login_a['access_token']}"}

        # 1. Jugador intenta acceder a ruta admin -> 403 Forbidden
        r_admin_forbidden = await cliente.get("/api/v1/test/admin-only", headers=bearer_p)
        assert r_admin_forbidden.status_code == 403
        assert r_admin_forbidden.json()["code"] == "permiso_denegado"

        # 2. Admin accede a ruta admin -> 200 OK
        r_admin_ok = await cliente.get("/api/v1/test/admin-only", headers=bearer_a)
        assert r_admin_ok.status_code == 200
        assert r_admin_ok.json()["admin_id"] == login_a["user_id"]

        # 3. Ambos pueden acceder a ruta jugador
        r_player_ok = await cliente.get("/api/v1/test/player-or-admin", headers=bearer_p)
        assert r_player_ok.status_code == 200
        assert r_player_ok.json()["rol"] == "PLAYER"

        r_admin_in_player = await cliente.get("/api/v1/test/player-or-admin", headers=bearer_a)
        assert r_admin_in_player.status_code == 200
        assert r_admin_in_player.json()["rol"] == "PLATFORM_ADMIN"

        # 4. Solicitud sin token -> 401 Unauthorized
        r_sin_token = await cliente.get("/api/v1/test/player-or-admin")
        assert r_sin_token.status_code == 401
        assert r_sin_token.json()["code"] == "credencial_invalida"

        # 5. Revocar sesión de jugador
        r_logout = await cliente.delete(_LOGOUT, headers=bearer_p)
        assert r_logout.status_code == 204

        # 6. Intentar acceder tras revocar -> 401 Unauthorized
        r_tras_logout = await cliente.get("/api/v1/test/player-or-admin", headers=bearer_p)
        assert r_tras_logout.status_code == 401
        assert r_tras_logout.json()["code"] == "credencial_invalida"


async def test_errores_validacion_y_proveedor_no_disponible(
    monkeypatch: pytest.MonkeyPatch,
    clave_rsa: rsa.RSAPrivateKey,
) -> None:
    """Verifica respuestas RFC 7807 ante ID tokens inválidos, cuerpos no JSON o fallo de red."""
    _simular_jwks(monkeypatch, clave_rsa)
    _configurar_entorno(monkeypatch)

    app = _crear_app_con_rutas_protegidas()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Cuerpo vacío / no JSON
        r_415 = await cliente.post(
            _LOGIN_STD, content=b"no json", headers={"Content-Type": "text/plain"}
        )
        assert r_415.status_code == 415
        assert r_415.json()["code"] == "json_requerido"

        # JSON sin id_token ni google_id_token
        r_422 = await cliente.post(_LOGIN_STD, json={"otro_campo": "valor"})
        assert r_422.status_code == 422
        assert r_422.json()["code"] == "solicitud_invalida"

        # ID token con firma inválida
        otra_clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token_invalido = _token_google(otra_clave)
        r_401 = await cliente.post(_LOGIN_STD, json={"id_token": token_invalido})
        assert r_401.status_code == 401
        assert r_401.json()["code"] == "google_credencial_invalida"

        # Proveedor Google no disponible (error de red o JWKS caído)
        def _jwks_caido() -> Any:
            raise PyJWKClientConnectionError("Timeout de conexión a Google")

        monkeypatch.setattr(identidad._google, "_claves", _jwks_caido)
        r_503 = await cliente.post(_LOGIN_STD, json={"id_token": token_invalido})
        assert r_503.status_code == 503
        assert r_503.json()["code"] == "identidad_no_disponible"
