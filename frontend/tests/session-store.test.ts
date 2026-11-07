/**
 * Pruebas unitarias de `session-store.ts` (almacenamiento en memoria, expiración,
 * invalidación y notificaciones a suscriptores).
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import {
  clearPlatformSession,
  configureSessionClockForTests,
  getActiveSessionSnapshot,
  getPlatformAccessToken,
  hasActivePlatformAdminSession,
  invalidatePlatformSessionOnUnauthorized,
  isValidOpaqueBearerFormat,
  setPlatformSession,
  subscribeToSessionChanges,
} from "../src/web-admin/modules/auth/services/session-store.ts";
import type { SessionChangeEvent } from "../src/web-admin/modules/auth/types/auth.types.ts";

const VALID_OPAQUE_TOKEN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopq"; // 43 chars URL-safe

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

test("almacena la sesión en memoria sin exponer el token en el snapshot público", () => {
  const snapshot = setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-001",
    role: "PLATFORM_ADMIN",
  });

  assert.ok(snapshot !== null);
  assert.equal(snapshot.userId, "admin-001");
  assert.equal(snapshot.role, "PLATFORM_ADMIN");
  assert.equal(snapshot.expiresAtMs, simulatedNowMs + 900_000);
  assert.equal("access_token" in snapshot, false);
  assert.equal("accessToken" in snapshot, false);
  assert.equal(getPlatformAccessToken(), VALID_OPAQUE_TOKEN);
  assert.equal(hasActivePlatformAdminSession(), true);
});

test("expira automáticamente la sesión cuando avanza el reloj y notifica 'expired'", () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 60,
    user_id: "admin-001",
    role: "PLATFORM_ADMIN",
  });

  const events: SessionChangeEvent[] = [];
  const unsubscribe = subscribeToSessionChanges((evt) => events.push(evt));

  try {
    // 59.9 segundos después sigue activa
    simulatedNowMs += 59_900;
    assert.equal(getPlatformAccessToken(), VALID_OPAQUE_TOKEN);
    assert.equal(events.length, 0);

    // Al llegar exactamente a los 60 segundos vence
    simulatedNowMs += 100;
    assert.equal(getPlatformAccessToken(), null);
    assert.equal(getActiveSessionSnapshot(), null);
    assert.equal(hasActivePlatformAdminSession(), false);
    assert.equal(events.length, 1);
    assert.equal(events[0]?.session, null);
    assert.equal(events[0]?.reason, "expired");
  } finally {
    unsubscribe();
  }
});

test("invalida la sesión ante un 401 y notifica 'unauthorized_401' a los consumidores", () => {
  const events: SessionChangeEvent[] = [];
  const unsubscribe = subscribeToSessionChanges((evt) => events.push(evt));

  try {
    setPlatformSession({
      access_token: VALID_OPAQUE_TOKEN,
      token_type: "Bearer",
      expires_in: 900,
      user_id: "admin-001",
      role: "PLATFORM_ADMIN",
    });

    invalidatePlatformSessionOnUnauthorized();

    assert.equal(getPlatformAccessToken(), null);
    assert.equal(getActiveSessionSnapshot(), null);
    assert.equal(events.length, 2);
    assert.equal(events[1]?.session, null);
    assert.equal(events[1]?.reason, "unauthorized_401");
  } finally {
    unsubscribe();
  }
});

test("rechaza sesiones con TTL no positivo o credenciales vacías", () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-001",
    role: "PLATFORM_ADMIN",
  });

  const invalidResult = setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 0,
    user_id: "admin-001",
    role: "PLATFORM_ADMIN",
  });

  assert.equal(invalidResult, null);
  assert.equal(getPlatformAccessToken(), null);
});

test("distingue el rol PLAYER de PLATFORM_ADMIN y valida el formato de Bearer opaco", () => {
  setPlatformSession({
    access_token: VALID_OPAQUE_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "player-001",
    role: "PLAYER",
  });

  assert.equal(getActiveSessionSnapshot()?.role, "PLAYER");
  assert.equal(hasActivePlatformAdminSession(), false);
  assert.equal(isValidOpaqueBearerFormat(VALID_OPAQUE_TOKEN), true);
  assert.equal(isValidOpaqueBearerFormat("short-token"), false);
});

test("ignora una respuesta 401 tardía de un token antiguo si ya se estableció una sesión nueva", () => {
  const OLD_TOKEN = "OLD_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars
  const NEW_TOKEN = "NEW_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars

  setPlatformSession({
    access_token: OLD_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-001",
    role: "PLATFORM_ADMIN",
  });

  // El administrador inicia una nueva sesión antes de que regrese un 401 viejo en vuelo
  setPlatformSession({
    access_token: NEW_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-001",
    role: "PLATFORM_ADMIN",
  });

  // Llega el 401 tardío asociado a OLD_TOKEN: NO debe invalidar NEW_TOKEN
  invalidatePlatformSessionOnUnauthorized(OLD_TOKEN);
  assert.equal(getPlatformAccessToken(), NEW_TOKEN);
  assert.equal(hasActivePlatformAdminSession(), true);

  // Si el 401 corresponde a NEW_TOKEN, sí invalida la sesión actual
  invalidatePlatformSessionOnUnauthorized(NEW_TOKEN);
  assert.equal(getPlatformAccessToken(), null);
  assert.equal(hasActivePlatformAdminSession(), false);
});
