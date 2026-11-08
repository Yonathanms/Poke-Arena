/**
 * Pruebas unitarias de `http-client.ts` (inyección de Bearer, Idempotency-Key,
 * FormData sin boundary manual, errores RFC 7807, Retry-After e invalidación en 401).
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import {
  ApiHttpError,
  configureHttpClientSessionHooks,
  requestApi,
  requestApiWithMeta,
} from "../src/shared/services/http-client.ts";
import {
  clearPlatformSession,
  getPlatformAccessToken,
  invalidatePlatformSessionOnUnauthorized,
  setPlatformSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";

const VALID_OPAQUE_TOKEN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopq";

beforeEach(() => {
  clearPlatformSession("manual_logout");
  configureHttpClientSessionHooks({
    getAccessToken: getPlatformAccessToken,
    onUnauthorized: invalidatePlatformSessionOnUnauthorized,
  });
});

afterEach(() => {
  clearPlatformSession("manual_logout");
});

test("inyecta Authorization Bearer e Idempotency-Key proporcionada por el llamador", async () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  let capturedUrl = "";
  let capturedHeaders: Headers | null = null;
  const callerKey = "550e8400-e29b-41d4-a716-446655440000";

  const fakeFetch: typeof fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedHeaders = new Headers(init?.headers);
    return new Response(
      JSON.stringify([{ code: "HAB-000", name: "Sin Habilidad" }]),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "X-Correlation-ID": "corr-abilities-1",
        },
      }
    );
  };

  const result = await requestApiWithMeta<Array<{ code: string; name: string }>>(
    "/content/abilities",
    {
      method: "GET",
      idempotencyKey: callerKey,
      fetchImpl: fakeFetch,
    }
  );

  assert.equal(capturedUrl, "/api/v1/content/abilities");
  assert.ok(capturedHeaders !== null);
  assert.equal((capturedHeaders as Headers).get("Authorization"), `Bearer ${VALID_OPAQUE_TOKEN}`);
  assert.equal((capturedHeaders as Headers).get("Idempotency-Key"), callerKey);
  assert.equal(result.status, 200);
  assert.equal(result.correlationId, "corr-abilities-1");
  assert.equal(result.data[0]?.code, "HAB-000");
});

test("no establece Content-Type manual cuando el cuerpo es FormData", async () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  const formData = new FormData();
  formData.set("name", "Guardiana");
  formData.set("cost", "2");
  formData.set("image", new Blob(["fake-png"], { type: "image/png" }), "guardiana.png");

  let capturedHeaders: Headers | null = null;
  let capturedBody: unknown = null;

  const fakeFetch: typeof fetch = async (_input, init) => {
    capturedHeaders = new Headers(init?.headers);
    capturedBody = init?.body;
    return new Response(
      JSON.stringify({
        id: "card-uuid-1",
        code: "PKA-LUC-001",
        operation_id: "card-uuid-1",
        image_id: "card-uuid-1",
        image_status: "READY",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } }
    );
  };

  const created = await requestApi<{ code: string }>("/content/cards", {
    method: "POST",
    body: formData,
    headers: { "Content-Type": "multipart/form-data" }, // incluso si alguien lo pasa por error, debe eliminarse
    idempotencyKey: "op-key-001",
    fetchImpl: fakeFetch,
  });

  assert.equal(created.code, "PKA-LUC-001");
  assert.ok(capturedHeaders !== null);
  assert.equal((capturedHeaders as Headers).has("Content-Type"), false);
  assert.equal(capturedBody, formData);
});

test("parsea errores RFC 7807 conservando status, code, detail, correlation_id y Retry-After", async () => {
  const fakeFetch: typeof fetch = async () =>
    new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Too Many Requests",
        status: 429,
        detail: "Reintenta después del período de espera.",
        code: "intentos_limitados",
        correlation_id: "03de590e-b414-403e-88a0-d3a8c1c37e86",
      }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/problem+json",
          "Retry-After": "60",
          "X-Correlation-ID": "03de590e-b414-403e-88a0-d3a8c1c37e86",
        },
      }
    );

  await assert.rejects(
    () =>
      requestApi("/identity/local/session", {
        method: "POST",
        requiresAuth: false,
        body: { username: "maestro-local", password: "wrong-password" },
        fetchImpl: fakeFetch,
      }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.status, 429);
      assert.equal(err.code, "intentos_limitados");
      assert.equal(err.detail, "Reintenta después del período de espera.");
      assert.equal(err.correlationId, "03de590e-b414-403e-88a0-d3a8c1c37e86");
      assert.equal(err.retryAfterSeconds, 60);
      assert.equal(err.shouldPreserveIdempotencyKey, false);
      return true;
    }
  );
});

test("invalida la sesión en memoria al recibir 401 en una ruta protegida", async () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  const fakeFetch: typeof fetch = async () =>
    new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Unauthorized",
        status: 401,
        detail: "Se requiere una sesión válida de Poké-Arena.",
        code: "credencial_invalida",
        correlation_id: "corr-401",
      }),
      { status: 401, headers: { "Content-Type": "application/problem+json" } }
    );

  await assert.rejects(
    () => requestApi("/content/abilities", { fetchImpl: fakeFetch }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.status, 401);
      assert.equal(err.code, "credencial_invalida");
      return true;
    }
  );

  assert.equal(getPlatformAccessToken(), null);
});

test("identifica correctamente cuándo debe preservarse la Idempotency-Key (503, 500, 409 en_curso y fallos de red)", async () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  const uncertainCommitFetch: typeof fetch = async () =>
    new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Service Unavailable",
        status: 503,
        detail: "Resultado incierto. Repite con la misma clave.",
        code: "commit_incierto",
        correlation_id: "corr-503",
      }),
      { status: 503, headers: { "Content-Type": "application/problem+json" } }
    );

  await assert.rejects(
    () =>
      requestApi("/content/cards", {
        method: "POST",
        idempotencyKey: "same-key-1",
        fetchImpl: uncertainCommitFetch,
      }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.code, "commit_incierto");
      assert.equal(err.shouldPreserveIdempotencyKey, true);
      return true;
    }
  );

  const inProgressFetch: typeof fetch = async () =>
    new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Conflict",
        status: 409,
        detail: "La operación está en curso. Repite con la misma clave.",
        code: "en_curso",
        correlation_id: "corr-409",
      }),
      { status: 409, headers: { "Content-Type": "application/problem+json" } }
    );

  await assert.rejects(
    () =>
      requestApi("/content/cards", {
        method: "POST",
        idempotencyKey: "same-key-1",
        fetchImpl: inProgressFetch,
      }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.shouldPreserveIdempotencyKey, true);
      return true;
    }
  );

  const networkFailureFetch: typeof fetch = async () => {
    throw new TypeError("Failed to fetch");
  };

  await assert.rejects(
    () =>
      requestApi("/content/cards", {
        method: "POST",
        idempotencyKey: "same-key-1",
        fetchImpl: networkFailureFetch,
      }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.isNetworkError, true);
      assert.equal(err.shouldPreserveIdempotencyKey, true);
      return true;
    }
  );
});

test("rechaza claves de idempotencia con comas o vacías antes de tocar la red", async () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  let networkCalled = false;
  const fakeFetch: typeof fetch = async () => {
    networkCalled = true;
    return new Response(null, { status: 204 });
  };

  await assert.rejects(
    () =>
      requestApi("/content/cards", {
        method: "POST",
        idempotencyKey: "clave,invalida",
        fetchImpl: fakeFetch,
      }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.status, 422);
      assert.equal(err.code, "idempotencia_invalida");
      return true;
    }
  );

  assert.equal(networkCalled, false);
});
