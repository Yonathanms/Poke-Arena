/**
 * Pruebas unitarias de `auth.api.ts` y mapeo de errores de `useAdminSession.ts`.
 *
 * Verifica:
 * - Solicitud correcta de login (`POST /api/v1/identity/local/session`).
 * - Respuesta 201 y activación de sesión en memoria sin exponer el token.
 * - Rechazo de roles no administrativos (`PLAYER`) y revocación best-effort del token.
 * - Validación de contrato de sesión malformado.
 * - Errores 401, 403, 404 (login local deshabilitado), 429 (`Retry-After`), 500/503 y fallos de red.
 * - Logout `204 No Content` sin parsear JSON y manejo explícito cuando falla la revocación remota.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import { ApiHttpError } from "../src/shared/services/http-client.ts";
import { mapAuthErrorToUserInfo } from "../src/web-admin/modules/auth/hooks/useAdminSession.ts";
import {
  activatePlatformAdminSession,
  loginWithLocalMasterAdmin,
  logoutPlatformSession,
  validateLocalLoginInput,
} from "../src/web-admin/modules/auth/services/auth.api.ts";
import {
  clearPlatformSession,
  configureSessionClockForTests,
  getActiveSessionSnapshot,
  getPlatformAccessToken,
  hasActivePlatformAdminSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";

const VALID_ADMIN_TOKEN = "ADM_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars
const VALID_PLAYER_TOKEN = "PLY_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars

let simulatedNowMs = 1_700_000_000_000;

beforeEach(() => {
  simulatedNowMs = 1_700_000_000_000;
  configureSessionClockForTests(() => simulatedNowMs);
  clearPlatformSession("manual_logout");
});

afterEach(() => {
  clearPlatformSession("manual_logout");
  configureSessionClockForTests();
});

test("envía POST /api/v1/identity/local/session y almacena la sesión 201 respetando expires_in", async () => {
  let capturedUrl = "";
  let capturedMethod = "";
  let capturedBody: Record<string, unknown> | null = null;

  const fakeFetch: typeof fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedMethod = init?.method ?? "GET";
    capturedBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return new Response(
      JSON.stringify({
        access_token: VALID_ADMIN_TOKEN,
        token_type: "Bearer",
        expires_in: 1200, // valor distinto de 900 para comprobar que usa el recibido
        user_id: "user-master-1",
        role: "PLATFORM_ADMIN",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } }
    );
  };

  const snapshot = await loginWithLocalMasterAdmin(
    { username: "  maestro-local  ", password: "secret-password-16chars" },
    { fetchImpl: fakeFetch }
  );

  assert.equal(capturedUrl, "/api/v1/identity/local/session");
  assert.equal(capturedMethod, "POST");
  assert.deepEqual(capturedBody, {
    username: "maestro-local",
    password: "secret-password-16chars",
  });
  assert.equal(snapshot.userId, "user-master-1");
  assert.equal(snapshot.role, "PLATFORM_ADMIN");
  assert.equal(snapshot.expiresAtMs, simulatedNowMs + 1_200_000);
  assert.equal("access_token" in snapshot, false);
  assert.equal(getPlatformAccessToken(), VALID_ADMIN_TOKEN);
  assert.equal(hasActivePlatformAdminSession(), true);
});

test("rechaza una sesión válida con rol PLAYER (403) y revoca el token para no dejarlo activo", async () => {
  const calls: Array<{ url: string; method: string; authHeader: string | null }> = [];

  const fakeFetch: typeof fetch = async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const headers = new Headers(init?.headers);
    calls.push({ url, method, authHeader: headers.get("Authorization") });

    if (url.endsWith("/identity/local/session")) {
      return new Response(
        JSON.stringify({
          access_token: VALID_PLAYER_TOKEN,
          token_type: "Bearer",
          expires_in: 900,
          user_id: "player-99",
          role: "PLAYER",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response(null, { status: 204 });
  };

  await assert.rejects(
    () =>
      loginWithLocalMasterAdmin(
        { username: "jugador", password: "password-player" },
        { fetchImpl: fakeFetch }
      ),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.status, 403);
      assert.equal(err.code, "permiso_denegado");
      return true;
    }
  );

  assert.equal(getPlatformAccessToken(), null);
  assert.equal(getActiveSessionSnapshot(), null);
  assert.equal(calls.length, 2);
  assert.equal(calls[1]?.url, "/api/v1/identity/session");
  assert.equal(calls[1]?.method, "DELETE");
  assert.equal(calls[1]?.authHeader, `Bearer ${VALID_PLAYER_TOKEN}`);
});

test("rechaza contratos de sesión incompletos o con token opaco inválido", async () => {
  await assert.rejects(
    () =>
      activatePlatformAdminSession({
        access_token: "token-corto-invalido",
        token_type: "Bearer",
        expires_in: 900,
        user_id: "admin-1",
        role: "PLATFORM_ADMIN",
      }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.status, 502);
      assert.equal(err.code, "respuesta_sesion_invalida");
      return true;
    }
  );
  assert.equal(getPlatformAccessToken(), null);
});

test("traduce correctamente errores 401, 403, 404, 429 (con Retry-After), 503 y fallos de red", async () => {
  const cases: Array<{
    status: number;
    code: string;
    detail: string;
    retryAfter?: string;
    expectedTitle: string;
    expectedRetry: number | null;
  }> = [
    {
      status: 401,
      code: "credencial_invalida",
      detail: "Credenciales inválidas.",
      expectedTitle: "Credenciales inválidas",
      expectedRetry: null,
    },
    {
      status: 403,
      code: "permiso_denegado",
      detail: "Se requiere el rol PLATFORM_ADMIN.",
      expectedTitle: "Permisos insuficientes",
      expectedRetry: null,
    },
    {
      status: 404,
      code: "http_error",
      detail: "La ruta no está disponible.",
      expectedTitle: "Autenticación local no disponible",
      expectedRetry: null,
    },
    {
      status: 429,
      code: "intentos_limitados",
      detail: "Reintenta después del período de espera.",
      retryAfter: "45",
      expectedTitle: "Demasiados intentos de inicio de sesión",
      expectedRetry: 45,
    },
    {
      status: 503,
      code: "identidad_no_disponible",
      detail: "Identidad no disponible.",
      expectedTitle: "Servicio de identidad no disponible",
      expectedRetry: null,
    },
  ];

  for (const item of cases) {
    const fakeFetch: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Error",
          status: item.status,
          detail: item.detail,
          code: item.code,
          correlation_id: `corr-${item.status}`,
        }),
        {
          status: item.status,
          headers: {
            "Content-Type": "application/problem+json",
            ...(item.retryAfter ? { "Retry-After": item.retryAfter } : {}),
          },
        }
      );

    await assert.rejects(
      () =>
        loginWithLocalMasterAdmin(
          { username: "maestro-local", password: "password" },
          { fetchImpl: fakeFetch }
        ),
      (err: unknown) => {
        const mapped = mapAuthErrorToUserInfo(err);
        assert.equal(mapped.status, item.status);
        assert.equal(mapped.code, item.code);
        assert.equal(mapped.title, item.expectedTitle);
        assert.equal(mapped.correlationId, `corr-${item.status}`);
        assert.equal(mapped.retryAfterSeconds, item.expectedRetry);
        return true;
      }
    );
  }

  // Fallo de red
  const networkFetch: typeof fetch = async () => {
    throw new TypeError("Network down");
  };
  await assert.rejects(
    () =>
      loginWithLocalMasterAdmin(
        { username: "maestro-local", password: "password" },
        { fetchImpl: networkFetch }
      ),
    (err: unknown) => {
      const mapped = mapAuthErrorToUserInfo(err);
      assert.equal(mapped.status, 0);
      assert.equal(mapped.title, "Sin conexión con el servidor");
      return true;
    }
  );
});

test("ejecuta logout DELETE /api/v1/identity/session (204 No Content) y limpia el estado local", async () => {
  await activatePlatformAdminSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  let capturedUrl = "";
  let capturedMethod = "";
  let capturedAuth: string | null = null;

  const fakeFetch: typeof fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedMethod = init?.method ?? "GET";
    capturedAuth = new Headers(init?.headers).get("Authorization");
    return new Response(null, { status: 204 });
  };

  const result = await logoutPlatformSession({ fetchImpl: fakeFetch });

  assert.equal(capturedUrl, "/api/v1/identity/session");
  assert.equal(capturedMethod, "DELETE");
  assert.equal(capturedAuth, `Bearer ${VALID_ADMIN_TOKEN}`);
  assert.equal(result.localSessionCleared, true);
  assert.equal(result.remoteRevocationConfirmed, true);
  assert.equal(result.warningMessage, null);
  assert.equal(getPlatformAccessToken(), null);
});

test("limpia la sesión local pero informa cuando la revocación remota falla por red o 503", async () => {
  await activatePlatformAdminSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  const failingFetch: typeof fetch = async () =>
    new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Service Unavailable",
        status: 503,
        detail: "Identidad no disponible.",
        code: "identidad_no_disponible",
        correlation_id: "corr-logout-503",
      }),
      { status: 503, headers: { "Content-Type": "application/problem+json" } }
    );

  const result = await logoutPlatformSession({ fetchImpl: failingFetch });

  assert.equal(getPlatformAccessToken(), null);
  assert.equal(result.localSessionCleared, true);
  assert.equal(result.remoteRevocationConfirmed, false);
  assert.ok(result.warningMessage && result.warningMessage.includes("no se pudo confirmar"));
  assert.equal(result.correlationId, "corr-logout-503");
});

test("valida la presencia y límites de longitud de usuario y contraseña sin filtrar secretos", () => {
  assert.ok(validateLocalLoginInput({ username: "   ", password: "secret" }) !== null);
  assert.ok(validateLocalLoginInput({ username: "admin", password: "" }) !== null);
  assert.ok(validateLocalLoginInput({ username: "a".repeat(64), password: "secret" }) !== null);
  assert.ok(
    validateLocalLoginInput({ username: "admin", password: "p".repeat(257) }) !== null
  );
  assert.equal(validateLocalLoginInput({ username: "admin", password: "secret" }), null);
});
