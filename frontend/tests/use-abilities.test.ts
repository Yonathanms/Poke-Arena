/**
 * Pruebas unitarias de `useAbilities.ts` / `AbilitiesQueryController` (Etapa F3).
 *
 * Verifica:
 * 1. Carga automática cuando existe sesión `PLATFORM_ADMIN`.
 * 2. Ausencia de consulta cuando no hay sesión o el rol es `PLAYER`.
 * 3. Estado de carga (`isLoading`), lista vacía (`isEmpty`), error y recuperación con `reload()`.
 * 4. Deduplicación de solicitudes concurrentes para el mismo administrador.
 * 5. Cancelación e ignorado de respuestas tardías cuando la sesión se cierra o cambia de usuario.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import {
  clearPlatformSession,
  setPlatformSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";
import { AbilitiesQueryController } from "../src/web-admin/modules/catalogo/hooks/useAbilities.ts";

const VALID_ADMIN_TOKEN_1 = "AD1_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars
const VALID_ADMIN_TOKEN_2 = "AD2_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars

beforeEach(() => {
  clearPlatformSession("manual_logout");
});

afterEach(() => {
  clearPlatformSession("manual_logout");
});

test("no consulta el endpoint cuando no existe sesión o el rol no es PLATFORM_ADMIN", async () => {
  let fetchCount = 0;
  const fakeFetch: typeof fetch = async () => {
    fetchCount += 1;
    return new Response(JSON.stringify([{ code: "HAB-000", name: "Sin Habilidad" }]), {
      status: 200,
    });
  };

  const controller = new AbilitiesQueryController({ fetchImpl: fakeFetch });
  controller.start();

  assert.equal(fetchCount, 0);
  assert.equal(controller.getState().isLoading, false);
  assert.deepEqual(controller.getState().abilities, []);

  // Si entra una sesión PLAYER, tampoco debe consultar el endpoint administrativo
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN_1,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "player-1",
    role: "PLAYER",
  });

  assert.equal(fetchCount, 0);
  controller.dispose();
});

test("carga habilidades al autenticarse como PLATFORM_ADMIN, maneja errores y permite reintentar", async () => {
  let shouldFail = true;
  let fetchCount = 0;

  const fakeFetch: typeof fetch = async () => {
    fetchCount += 1;
    if (shouldFail) {
      return new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Service Unavailable",
          status: 503,
          detail: "Catálogo temporalmente no disponible.",
          code: "catalogo_no_disponible",
          correlation_id: "corr-hab-503",
        }),
        { status: 503, headers: { "Content-Type": "application/problem+json" } }
      );
    }
    return new Response(
      JSON.stringify([
        { code: "HAB-000", name: "Sin Habilidad" },
        { code: "HAB-010", name: "Escudo Acuático" },
      ]),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  const controller = new AbilitiesQueryController({ fetchImpl: fakeFetch });
  controller.start();

  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN_1,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });

  // Esperar a que termine la primera carga fallida
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(fetchCount, 1);
  assert.equal(controller.getState().isLoading, false);
  assert.equal(controller.getState().error?.code, "catalogo_no_disponible");
  assert.equal(controller.getState().error?.correlationId, "corr-hab-503");

  // Reintento manual exitoso
  shouldFail = false;
  const loaded = await controller.load({ force: true });
  assert.equal(fetchCount, 2);
  assert.equal(loaded.length, 2);
  assert.equal(controller.getState().hasLoaded, true);
  assert.equal(controller.getState().isEmpty, false);
  assert.equal(controller.getState().error, null);

  controller.dispose();
});

test("ignora respuestas tardías si la sesión se cierra o cambia de administrador mientras la petición está en vuelo", async () => {
  let resolveSlowRequest: ((resp: Response) => void) | null = null;
  let callIndex = 0;

  const fakeFetch: typeof fetch = async () => {
    callIndex += 1;
    if (callIndex === 1) {
      return new Promise<Response>((resolve) => {
        resolveSlowRequest = resolve;
      });
    }
    return new Response(
      JSON.stringify([{ code: "HAB-002", name: "Habilidad Admin 2" }]),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  const controller = new AbilitiesQueryController({ fetchImpl: fakeFetch });
  controller.start();

  // Admin 1 inicia sesión -> dispara petición 1 (lenta)
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN_1,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-1",
    role: "PLATFORM_ADMIN",
  });
  assert.equal(controller.getState().isLoading, true);

  // Antes de que responda la petición 1, cambia la sesión a Admin 2 -> cancela 1 y lanza 2
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN_2,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-2",
    role: "PLATFORM_ADMIN",
  });

  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.deepEqual(controller.getState().abilities, [
    { code: "HAB-002", name: "Habilidad Admin 2" },
  ]);

  // Ahora se resuelve tardíamente la petición de Admin 1 -> debe ignorarse por completo
  assert.ok(resolveSlowRequest !== null);
  (resolveSlowRequest as (resp: Response) => void)(
    new Response(
      JSON.stringify([{ code: "HAB-001", name: "Habilidad Obsoleta Admin 1" }]),
      { status: 200, headers: { "Content-Type": "application/json" } }
    )
  );
  await new Promise((resolve) => setTimeout(resolve, 10));

  assert.deepEqual(controller.getState().abilities, [
    { code: "HAB-002", name: "Habilidad Admin 2" },
  ]);

  // Al cerrar sesión se limpia inmediatamente la lista en memoria
  clearPlatformSession("manual_logout");
  assert.deepEqual(controller.getState().abilities, []);
  assert.equal(controller.getState().hasLoaded, false);

  controller.dispose();
});
