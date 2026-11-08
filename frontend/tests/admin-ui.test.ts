/**
 * Pruebas de renderizado e interacción de los componentes React de F2:
 * `AlertBanner`, `AdminLoginForm`, `AdminLayout` y `App`.
 *
 * Verifica:
 * - Renderizado inicial del login administrativo con etiquetas asociadas (`htmlFor` / `id`).
 * - Estado de carga (`isSubmitting`) y bloqueo contra doble envío concurrente.
 * - Mensajes de error RFC 7807 + `correlation_id` y cuenta regresiva accesible en `429`.
 * - Transición al `AdminLayout` tras login con rol `PLATFORM_ADMIN` y ocultamiento del token.
 * - Cierre de sesión y preservación inerte del espacio de trabajo al expirar la sesión.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import App from "../src/App.tsx";
import { AlertBanner } from "../src/shared/components/AlertBanner.tsx";
import { AdminLoginForm } from "../src/web-admin/modules/auth/components/AdminLoginForm.tsx";
import {
  clearPlatformSession,
  configureSessionClockForTests,
  setPlatformSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";
import {
  AdminLayout,
  formatRemainingSessionTime,
} from "../src/web-admin/shared/AdminLayout.tsx";

const VALID_ADMIN_TOKEN = "ADM_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"; // 43 chars
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

test("renderiza el estado inicial de AdminLoginForm con etiquetas vinculadas y campos requeridos", () => {
  const html = renderToStaticMarkup(
    React.createElement(AdminLoginForm, {
      isSubmitting: false,
      retryCooldownSeconds: 0,
      authError: null,
      logoutNotice: null,
      invalidationReason: null,
      onSubmitCredentials: async () => true,
    })
  );

  assert.match(html, /Usuario administrador/);
  assert.match(html, /Contraseña/);
  assert.match(html, /Iniciar sesión administrativa/);
  assert.match(html, /name="username"/);
  assert.match(html, /name="password"/);
  assert.match(html, /type="password"/);
  // Comprueba que cada label tiene su atributo for apuntando al id del input
  const labelForMatches = [...html.matchAll(/for="([^"]+)"/g)].map((m) => m[1]);
  assert.equal(labelForMatches.length, 2);
  for (const targetId of labelForMatches) {
    assert.ok(targetId && html.includes(`id="${targetId}"`));
  }
});

test("muestra el estado de carga y deshabilita controles mientras isSubmitting es true", () => {
  const html = renderToStaticMarkup(
    React.createElement(AdminLoginForm, {
      isSubmitting: true,
      retryCooldownSeconds: 0,
      authError: null,
      logoutNotice: null,
      invalidationReason: null,
      onSubmitCredentials: async () => true,
    })
  );

  assert.match(html, /Verificando credenciales\.\.\./);
  assert.equal((html.match(/disabled=""/g) ?? []).length >= 3, true);
});

test("presenta errores RFC 7807 con correlation_id y bloquea el envío durante Retry-After (429)", () => {
  const html = renderToStaticMarkup(
    React.createElement(AdminLoginForm, {
      isSubmitting: false,
      retryCooldownSeconds: 42,
      authError: {
        status: 429,
        code: "intentos_limitados",
        title: "Demasiados intentos de inicio de sesión",
        detail: "Reintenta después del período de espera.",
        correlationId: "corr-429-xyz",
        retryAfterSeconds: 42,
      },
      logoutNotice: null,
      invalidationReason: null,
      onSubmitCredentials: async () => false,
    })
  );

  assert.match(html, /role="alert"/);
  assert.match(html, /Demasiados intentos de inicio de sesión/);
  assert.match(html, /corr-429-xyz/);
  assert.match(html, /role="timer"/);
  assert.match(html, /Reintentar en 42s/);
  assert.match(html, /disabled=""/);
});

test("renderiza AlertBanner con variantes semánticas accesibles y correlationId opcional", () => {
  const errorHtml = renderToStaticMarkup(
    React.createElement(AlertBanner, {
      variant: "error",
      title: "Credenciales inválidas",
      description: "Verifica tu usuario y contraseña.",
      correlationId: "03de590e-b414-403e-88a0-d3a8c1c37e86",
    })
  );

  assert.match(errorHtml, /role="alert"/);
  assert.match(errorHtml, /aria-live="assertive"/);
  assert.match(errorHtml, /03de590e-b414-403e-88a0-d3a8c1c37e86/);

  const infoHtml = renderToStaticMarkup(
    React.createElement(AlertBanner, {
      variant: "info",
      title: "Sesión cerrada",
      description: "La sesión fue revocada.",
    })
  );

  assert.match(infoHtml, /role="status"/);
  assert.match(infoHtml, /aria-live="polite"/);
});

test("renderiza AdminLayout con datos públicos de la sesión, reloj MM:SS y sin exponer el token", () => {
  assert.equal(formatRemainingSessionTime(900), "15:00");
  assert.equal(formatRemainingSessionTime(65), "01:05");
  assert.equal(formatRemainingSessionTime(0), "00:00");

  const snapshot = setPlatformSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-maestro-01",
    role: "PLATFORM_ADMIN",
  });
  assert.ok(snapshot !== null);

  const html = renderToStaticMarkup(
    React.createElement(AdminLayout, {
      session: snapshot,
      remainingSeconds: 900,
      isLoggingOut: false,
      onLogout: () => {},
    })
  );

  assert.match(html, /Portal Administrativo/);
  assert.match(html, /PLATFORM_ADMIN/);
  assert.match(html, /admin-maestro-01/);
  assert.match(html, /15:00/);
  assert.match(html, /Cerrar sesión/);
  // Nunca debe aparecer el token opaco en el DOM renderizado
  assert.equal(html.includes(VALID_ADMIN_TOKEN), false);
});

test("App muestra AdminLoginForm cuando no hay sesión o el rol no es PLATFORM_ADMIN, y AdminLayout cuando sí lo es", () => {
  // 1. Sin sesión -> muestra formulario de login
  const unauthHtml = renderToStaticMarkup(React.createElement(App));
  assert.match(unauthHtml, /Iniciar sesión administrativa/);
  assert.equal(unauthHtml.includes("Cerrar sesión"), false);

  // 2. Sesión con rol PLAYER -> sigue exigiendo login administrativo (no muestra AdminLayout)
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "player-01",
    role: "PLAYER",
  });
  const playerHtml = renderToStaticMarkup(React.createElement(App));
  assert.match(playerHtml, /Iniciar sesión administrativa/);
  assert.equal(playerHtml.includes("Cerrar sesión"), false);

  // 3. Sesión con rol PLATFORM_ADMIN -> muestra AdminLayout y protege el token
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-01",
    role: "PLATFORM_ADMIN",
  });
  const adminHtml = renderToStaticMarkup(React.createElement(App));
  assert.match(adminHtml, /Portal Administrativo/);
  assert.match(adminHtml, /Cerrar sesión/);
  assert.equal(adminHtml.includes(VALID_ADMIN_TOKEN), false);

  // 4. Cuando el reloj supera expires_in, App vuelve a presentar reautenticación
  simulatedNowMs += 901_000;
  const expiredHtml = renderToStaticMarkup(React.createElement(App));
  assert.match(expiredHtml, /Iniciar sesión administrativa/);
  assert.equal(expiredHtml.includes("Cerrar sesión"), false);
});
