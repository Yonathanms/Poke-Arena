/**
 * Pruebas unitarias de `catalog.api.ts` (Etapa F3).
 *
 * Verifica:
 * 1. GET `/api/v1/content/abilities` correcto con inyección del Bearer token.
 * 2. Validación estricta del payload de habilidades y soporte de lista vacía (`[]`).
 * 3. Manejo de errores 401 (con invalidación de sesión), 403, 500/503 y fallos de red.
 * 4. Construcción exacta del `FormData` para POST `/api/v1/content/cards` (7 campos, sin duplicados).
 * 5. Presencia de `Idempotency-Key` proporcionada por el llamador y ausencia de `Content-Type` manual.
 * 6. Interpretación del resultado HTTP 201 (`CardCreatedResponseDTO` con `image_status: "READY"`).
 * 7. Manejo de errores RFC 7807 y ausencia total de reintentos automáticos o rotación de clave.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import { ApiHttpError } from "../src/shared/services/http-client.ts";
import {
  clearPlatformSession,
  getPlatformAccessToken,
  setPlatformSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";
import {
  buildCreateCardFormData,
  fetchSelectableAbilities,
  submitCreateCardMultipart,
} from "../src/web-admin/modules/catalogo/services/catalog.api.ts";

const VALID_ADMIN_TOKEN = "ADM_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars

beforeEach(() => {
  clearPlatformSession("manual_logout");
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-f3",
    role: "PLATFORM_ADMIN",
  });
});

afterEach(() => {
  clearPlatformSession("manual_logout");
});

test("consulta GET /api/v1/content/abilities inyectando el Bearer token y validando el payload", async () => {
  let capturedUrl = "";
  let capturedMethod = "";
  let capturedAuth: string | null = null;

  const fakeFetch: typeof fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedMethod = init?.method ?? "GET";
    capturedAuth = new Headers(init?.headers).get("Authorization");
    return new Response(
      JSON.stringify([
        { code: "HAB-000", name: "Sin Habilidad" },
        { code: "HAB-001", name: "Impulso Ígneo" },
      ]),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  const abilities = await fetchSelectableAbilities({ fetchImpl: fakeFetch });

  assert.equal(capturedUrl, "/api/v1/content/abilities");
  assert.equal(capturedMethod, "GET");
  assert.equal(capturedAuth, `Bearer ${VALID_ADMIN_TOKEN}`);
  assert.deepEqual(abilities, [
    { code: "HAB-000", name: "Sin Habilidad" },
    { code: "HAB-001", name: "Impulso Ígneo" },
  ]);
});

test("acepta una lista vacía [] en GET /api/v1/content/abilities y rechaza payloads malformados", async () => {
  const emptyFetch: typeof fetch = async () =>
    new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  const emptyList = await fetchSelectableAbilities({ fetchImpl: emptyFetch });
  assert.deepEqual(emptyList, []);

  const invalidPayloadFetch: typeof fetch = async () =>
    new Response(JSON.stringify([{ code: "INVALID-CODE", name: "" }]), {
      status: 200,
      headers: { "Content-Type": "application/json", "X-Correlation-ID": "corr-bad-hab" },
    });

  await assert.rejects(
    () => fetchSelectableAbilities({ fetchImpl: invalidPayloadFetch }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.status, 502);
      assert.equal(err.code, "respuesta_habilidades_invalida");
      assert.equal(err.correlationId, "corr-bad-hab");
      return true;
    }
  );
});

test("propaga errores 401 (invalidando sesión), 403, 503 y fallos de red al consultar habilidades", async () => {
  const statusCases = [
    { status: 401, code: "credencial_invalida", detail: "Sesión vencida." },
    { status: 403, code: "permiso_denegado", detail: "Rol insuficiente." },
    { status: 503, code: "catalogo_no_disponible", detail: "Catálogo no disponible." },
  ];

  for (const item of statusCases) {
    setPlatformSession({
      access_token: VALID_ADMIN_TOKEN,
      token_type: "Bearer",
      expires_in: 900,
      user_id: "admin-f3",
      role: "PLATFORM_ADMIN",
    });

    const errorFetch: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Error",
          status: item.status,
          detail: item.detail,
          code: item.code,
          correlation_id: `corr-${item.status}`,
        }),
        { status: item.status, headers: { "Content-Type": "application/problem+json" } }
      );

    await assert.rejects(
      () => fetchSelectableAbilities({ fetchImpl: errorFetch }),
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.equal(err.status, item.status);
        assert.equal(err.code, item.code);
        assert.equal(err.correlationId, `corr-${item.status}`);
        return true;
      }
    );

    if (item.status === 401) {
      assert.equal(getPlatformAccessToken(), null);
    }
  }

  // Reestablecer sesión para probar fallo de red
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-f3",
    role: "PLATFORM_ADMIN",
  });

  const networkErrorFetch: typeof fetch = async () => {
    throw new TypeError("Failed to fetch");
  };

  await assert.rejects(
    () => fetchSelectableAbilities({ fetchImpl: networkErrorFetch }),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.isNetworkError, true);
      assert.equal(err.status, 0);
      return true;
    }
  );
});

test("construye el FormData exacto de 7 campos y envía POST /api/v1/content/cards sin Content-Type manual", async () => {
  const imageBlob = new Blob(["png-binary-content"], { type: "image/png" });
  const formData = buildCreateCardFormData({
    name: "  Guardiana Solar  ",
    cost: 2,
    power: -5,
    card_type: "LUC",
    rarity: "RARA",
    ability_code: "HAB-000",
    image: imageBlob,
    imageFileName: "guardiana.png",
  });

  const entries = [...formData.entries()];
  assert.equal(entries.length, 7);
  assert.equal(formData.get("name"), "Guardiana Solar");
  assert.equal(formData.get("cost"), "2");
  assert.equal(formData.get("power"), "-5");
  assert.equal(formData.get("card_type"), "LUC");
  assert.equal(formData.get("rarity"), "RARA");
  assert.equal(formData.get("ability_code"), "HAB-000");
  const uploadedFile = formData.get("image");
  assert.ok(uploadedFile instanceof File);
  assert.equal(uploadedFile.name, "guardiana.png");

  let capturedUrl = "";
  let capturedMethod = "";
  let capturedHeaders: Headers | null = null;
  let capturedBody: unknown = null;
  const callerKey = "c7a6e0ec-8b2f-4e1a-9c0d-123456789abc";

  const fakeFetch: typeof fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedMethod = init?.method ?? "GET";
    capturedHeaders = new Headers(init?.headers);
    capturedBody = init?.body;
    return new Response(
      JSON.stringify({
        id: "03de590e-b414-403e-88a0-d3a8c1c37e86",
        code: "PKA-LUC-001",
        operation_id: "03de590e-b414-403e-88a0-d3a8c1c37e86",
        image_id: "03de590e-b414-403e-88a0-d3a8c1c37e86",
        image_status: "READY",
      }),
      {
        status: 201,
        headers: {
          "Content-Type": "application/json",
          "X-Correlation-ID": "03de590e-b414-403e-88a0-d3a8c1c37e86",
        },
      }
    );
  };

  const response = await submitCreateCardMultipart(
    {
      name: "  Guardiana Solar  ",
      cost: 2,
      power: -5,
      card_type: "LUC",
      rarity: "RARA",
      ability_code: "HAB-000",
      image: imageBlob,
      imageFileName: "guardiana.png",
    },
    callerKey,
    { fetchImpl: fakeFetch }
  );

  assert.equal(capturedUrl, "/api/v1/content/cards");
  assert.equal(capturedMethod, "POST");
  assert.ok(capturedHeaders !== null);
  assert.equal((capturedHeaders as Headers).get("Authorization"), `Bearer ${VALID_ADMIN_TOKEN}`);
  assert.equal((capturedHeaders as Headers).get("Idempotency-Key"), callerKey);
  assert.equal((capturedHeaders as Headers).has("Content-Type"), false);
  assert.ok(capturedBody instanceof FormData);
  assert.equal(response.status, 201);
  assert.equal(response.data.code, "PKA-LUC-001");
  assert.equal(response.data.image_status, "READY");
  assert.equal(response.correlationId, "03de590e-b414-403e-88a0-d3a8c1c37e86");
});

test("no realiza reintentos automáticos ni rota Idempotency-Key ante errores RFC 7807 en POST /content/cards", async () => {
  let invocationCount = 0;
  let receivedKey = "";

  const failingFetch: typeof fetch = async (_input, init) => {
    invocationCount += 1;
    receivedKey = new Headers(init?.headers).get("Idempotency-Key") ?? "";
    return new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Service Unavailable",
        status: 503,
        detail: "Resultado incierto. Repite con la misma clave.",
        code: "commit_incierto",
        correlation_id: "corr-commit-incierto",
      }),
      { status: 503, headers: { "Content-Type": "application/problem+json" } }
    );
  };

  const callerKey = "fixed-caller-key-001";

  await assert.rejects(
    () =>
      submitCreateCardMultipart(
        {
          name: "Guardiana",
          cost: 2,
          power: 5,
          card_type: "AGU",
          rarity: "RARA",
          ability_code: "HAB-000",
          image: new Blob(["bytes"], { type: "image/png" }),
        },
        callerKey,
        { fetchImpl: failingFetch }
      ),
    (err: unknown) => {
      assert.ok(err instanceof ApiHttpError);
      assert.equal(err.status, 503);
      assert.equal(err.code, "commit_incierto");
      assert.equal(err.shouldPreserveIdempotencyKey, true);
      return true;
    }
  );

  // Exactamente 1 intento: catalog.api.ts nunca reintenta por su cuenta
  assert.equal(invocationCount, 1);
  assert.equal(receivedKey, callerKey);
});
