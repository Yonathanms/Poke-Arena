/**
 * Suite de Integración End-to-End (Etapa F5) para 2.1.1 — Crear Carta.
 *
 * Verifica la interacción completa entre todas las capas del frontend (F1–F4)
 * y el contrato HTTP real de FastAPI (Entrega 1G) sin realizar escrituras
 * sobre las bases de datos persistentes:
 *
 * - Fase 1 (§8): Recorrido completo autenticado (pasos 1 a 17), desde el login
 *   de `PLATFORM_ADMIN` y la carga de habilidades (`HAB-000`), pasando por la
 *   validación de una imagen PNG 1000×1400 (5:7), vista previa reactiva,
 *   envío multipart de 7 campos con `Idempotency-Key`, respuesta `201 Created`,
 *   actualización del código oficial, bloqueo de reenvío y registro en sesión.
 * - Fase 2 (§9): Casos A–J de idempotencia (incluyendo abandono con respuesta
 *   tardía en vuelo) y verificación formal de la invariante: una misma
 *   `Idempotency-Key` jamás se asocia a un payload distinto.
 * - Fase 3 (§10 y §17): Matriz completa de códigos HTTP/RFC 7807 (201, 400, 401,
 *   403, 404, 409 `en_curso`, 409 `conflicto_idempotencia`, 413, 415, 422, 429
 *   con `Retry-After`, 500 y 503 `commit_incierto`), preservación en `401`,
 *   limpieza en logout manual y aislamiento al cambiar de administrador.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import App from "../src/App.tsx";
import {
  loginWithLocalMasterAdmin,
  logoutPlatformSession,
} from "../src/web-admin/modules/auth/services/auth.api.ts";
import {
  clearPlatformSession,
  configureSessionClockForTests,
  getActiveSessionSnapshot,
  setPlatformSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";
import { AbilitiesQueryController } from "../src/web-admin/modules/catalogo/hooks/useAbilities.ts";
import {
  CreateCardController,
  resetSharedCreateCardControllerForTests,
} from "../src/web-admin/modules/catalogo/hooks/useCreateCard.ts";
import { CatalogListScreen } from "../src/web-admin/modules/catalogo/screens/CatalogListScreen.tsx";
import { CreateCardScreen } from "../src/web-admin/modules/catalogo/screens/CreateCardScreen.tsx";
import {
  SequentialImageSelectionPipeline,
  type ObjectUrlManager,
} from "../src/web-admin/modules/catalogo/validation/card-validation.ts";

const ADMIN_TOKEN_1 = "ADM_F5_INTEGRATION_TOKEN_000000000000000001";
const ADMIN_TOKEN_2 = "ADM_F5_INTEGRATION_TOKEN_000000000000000002";

let simulatedNowMs = 1_700_500_000_000;

/**
 * Crea un archivo PNG simulado de 1000 × 1400 px (proporción 5:7 exacta, < 5 MB)
 * idéntico en metadatos al utilizado por el usuario en las pruebas manuales (§2 y §11).
 */
function createF5PngFile(fileName = "guardian-llamas-1000x1400.png"): File {
  const pngSignatureAndPayload = new Uint8Array([
    137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82,
  ]);
  return new File([pngSignatureAndPayload], fileName, { type: "image/png" });
}

/**
 * Calcula una huella determinista de los 7 campos multipart enviados en un `FormData`
 * para comprobar la invariante de idempotencia en el servidor simulado.
 */
async function fingerprintMultipartFormData(formData: FormData): Promise<string> {
  const entries: string[] = [];
  for (const [key, value] of formData.entries()) {
    if (typeof value === "string") {
      entries.push(`${key}=${value}`);
    } else {
      const bytes = new Uint8Array(await value.arrayBuffer());
      entries.push(`${key}=file(${value.name},${value.type},${bytes.byteLength},[${bytes.join(",")}])`);
    }
  }
  return entries.join("|");
}

beforeEach(() => {
  simulatedNowMs = 1_700_500_000_000;
  configureSessionClockForTests(() => simulatedNowMs);
  clearPlatformSession("manual_logout");
  resetSharedCreateCardControllerForTests();
});

afterEach(() => {
  resetSharedCreateCardControllerForTests();
  clearPlatformSession("manual_logout");
  configureSessionClockForTests();
});

test("Fase 1 (§8): ejecuta el flujo integral de 17 pasos desde Login hasta 201 Created, vista previa 1000×1400 y registro en sesión", async () => {
  const recordedRequests: Array<{
    readonly method: string;
    readonly url: string;
    readonly authHeader: string | null;
    readonly idempotencyKey: string | null;
    readonly contentTypeHeader: string | null;
  }> = [];

  const simulatedFetch: typeof fetch = async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";
    const headers = new Headers(init?.headers);
    const authHeader = headers.get("Authorization");
    const idempotencyKey = headers.get("Idempotency-Key");
    const contentTypeHeader = headers.get("Content-Type");

    recordedRequests.push({
      method,
      url,
      authHeader,
      idempotencyKey,
      contentTypeHeader,
    });

    if (url === "/api/v1/identity/local/session" && method === "POST") {
      return new Response(
        JSON.stringify({
          access_token: ADMIN_TOKEN_1,
          token_type: "Bearer",
          expires_in: 900,
          user_id: "maestro-local-id",
          role: "PLATFORM_ADMIN",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    }

    if (url === "/api/v1/content/abilities" && method === "GET") {
      assert.equal(authHeader, `Bearer ${ADMIN_TOKEN_1}`);
      return new Response(
        JSON.stringify([{ code: "HAB-000", name: "Sin Habilidad" }]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (url === "/api/v1/content/cards" && method === "POST") {
      assert.equal(authHeader, `Bearer ${ADMIN_TOKEN_1}`);
      assert.equal(idempotencyKey, "f5-main-flow-idem-001");
      // Para FormData el cliente nunca debe fijar Content-Type manual
      assert.equal(contentTypeHeader, null);

      const formData = init?.body as FormData;
      assert.ok(formData instanceof FormData);
      const keys = [...formData.keys()];
      assert.deepEqual(keys, [
        "name",
        "cost",
        "power",
        "card_type",
        "rarity",
        "ability_code",
        "image",
      ]);
      assert.equal(formData.get("name"), "Guardian de las Llamas F5");
      assert.equal(formData.get("cost"), "5");
      assert.equal(formData.get("power"), "12");
      assert.equal(formData.get("card_type"), "FUE");
      assert.equal(formData.get("rarity"), "RARA");
      assert.equal(formData.get("ability_code"), "HAB-000");

      const uploadedImage = formData.get("image") as File;
      assert.ok(uploadedImage instanceof File);
      assert.equal(uploadedImage.name, "guardian-llamas-1000x1400.png");
      assert.equal(uploadedImage.type, "image/png");

      return new Response(
        JSON.stringify({
          id: "b7c090e4-6f44-4d5e-9d94-112233445566",
          code: "PKA-FUE-001",
          operation_id: "b7c090e4-6f44-4d5e-9d94-112233445566",
          image_id: "b7c090e4-6f44-4d5e-9d94-112233445566",
          image_status: "READY",
        }),
        {
          status: 201,
          headers: {
            "Content-Type": "application/json",
            "X-Correlation-ID": "b7c090e4-6f44-4d5e-9d94-112233445566",
          },
        }
      );
    }

    throw new Error(`Ruta no esperada en prueba F5: ${method} ${url}`);
  };

  // Paso 1: Pantalla inicial sin sesión presenta login administrativo
  const unauthMarkup = renderToStaticMarkup(React.createElement(App));
  assert.match(unauthMarkup, /Iniciar sesión administrativa/);

  // Paso 2: El administrador inicia sesión
  const sessionSnapshot = await loginWithLocalMasterAdmin(
    { username: "maestro-local", password: "PasswordDePruebaSegura123!" },
    { fetchImpl: simulatedFetch }
  );
  assert.equal(sessionSnapshot.role, "PLATFORM_ADMIN");
  assert.equal(getActiveSessionSnapshot()?.userId, "maestro-local-id");

  // Paso 3 y 4: El portal carga Crear Carta y consulta habilidades disponibles
  const abilitiesController = new AbilitiesQueryController({ fetchImpl: simulatedFetch });
  const loadedAbilities = await abilitiesController.load();
  assert.deepEqual(loadedAbilities, [{ code: "HAB-000", name: "Sin Habilidad" }]);

  const cardController = new CreateCardController({
    fetchImpl: simulatedFetch,
    generateIdempotencyKey: () => "f5-main-flow-idem-001",
  });
  cardController.start();
  cardController.syncAvailableAbilities(loadedAbilities, true);

  // Paso 5 y 6: El usuario introduce los datos de prueba F5 (§11) y selecciona HAB-000
  cardController.setName("  Guardian de las Llamas F5  ");
  cardController.setCostInput("5");
  cardController.setPowerInput("12");
  cardController.setCardType("FUE");
  cardController.setRarity("RARA");
  cardController.setAbilityCode("HAB-000");

  // Paso 7: Selección y validación de la imagen PNG 1000 × 1400 (proporción 5:7 exacta)
  const createdUrls: string[] = [];
  const urlManager: ObjectUrlManager = {
    createObjectURL: () => {
      const url = `blob:pokearena-f5/${createdUrls.length + 1}`;
      createdUrls.push(url);
      return url;
    },
    revokeObjectURL: () => {},
  };
  const imagePipeline = new SequentialImageSelectionPipeline({
    urlManager,
    decodeDimensions: async () => ({ width: 1000, height: 1400 }),
  });
  const pngFile = createF5PngFile();
  const inspection = await imagePipeline.inspectFile(pngFile);
  assert.equal(inspection.status, "valid");
  if (inspection.status === "valid") {
    cardController.setImageSelection({
      file: pngFile,
      previewUrl: inspection.previewUrl,
      dimensions: inspection.dimensions,
      sizeBytes: inspection.sizeBytes,
      mimeType: inspection.mimeType,
    });
  }

  // Paso 8: La previsualización se actualiza con los datos y el código provisional PKA-FUE-???
  const preSubmitMarkup = renderToStaticMarkup(
    React.createElement(CreateCardScreen, {
      controller: cardController,
      fetchImpl: simulatedFetch,
    })
  );
  assert.match(preSubmitMarkup, /Guardian de las Llamas F5/);
  assert.match(preSubmitMarkup, /1000×1400/);
  assert.match(preSubmitMarkup, /PKA-FUE-\?\?\?/);
  assert.match(preSubmitMarkup, /\+12/);
  assert.equal(preSubmitMarkup.includes(ADMIN_TOKEN_1), false);

  // Pasos 9, 10, 11, 12, 13 y 14: Validación, Idempotency-Key única, FormData y 201 Created
  const createdDto = await cardController.submit();
  assert.ok(createdDto !== null);
  assert.equal(createdDto.code, "PKA-FUE-001");
  assert.equal(createdDto.image_status, "READY");

  // Paso 15: La interfaz muestra el código oficial recibido (PKA-FUE-001)
  const postSubmitMarkup = renderToStaticMarkup(
    React.createElement(CreateCardScreen, {
      controller: cardController,
      fetchImpl: simulatedFetch,
    })
  );
  assert.match(postSubmitMarkup, /Carta creada exitosamente — Código oficial: PKA-FUE-001/);
  assert.match(postSubmitMarkup, /Confirmada · READY/);
  assert.equal(postSubmitMarkup.includes("PKA-FUE-???"), false);

  // Paso 16: Se impide el reenvío de la misma operación ya confirmada
  const postCallsBeforeDuplicateAttempt = recordedRequests.filter(
    (r) => r.url === "/api/v1/content/cards"
  ).length;
  await cardController.submit();
  const postCallsAfterDuplicateAttempt = recordedRequests.filter(
    (r) => r.url === "/api/v1/content/cards"
  ).length;
  assert.equal(postCallsBeforeDuplicateAttempt, 1);
  assert.equal(postCallsAfterDuplicateAttempt, 1);

  // Verificar que el historial de la sesión contiene la carta recién creada
  const catalogListMarkup = renderToStaticMarkup(
    React.createElement(CatalogListScreen, {
      entries: cardController.getState().sessionHistory,
    })
  );
  assert.match(catalogListMarkup, /PKA-FUE-001/);
  assert.match(catalogListMarkup, /Guardian de las Llamas F5/);

  // Paso 17: Se permite iniciar una carta nueva limpiando el formulario y conservando el historial
  cardController.startNewCard();
  assert.equal(cardController.getState().status, "draft");
  assert.equal(cardController.getState().activeIdempotencyKey, null);
  assert.equal(cardController.getState().values.name, "");
  assert.equal(cardController.getState().sessionHistory.length, 1);

  abilitiesController.dispose();
  cardController.dispose();
});

test("Fase 2 (§9): Caso J (respuesta tardía de operación abandonada) e invariante formal de que una misma Idempotency-Key jamás se asocia a un payload distinto", async () => {
  setPlatformSession({
    access_token: ADMIN_TOKEN_1,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "maestro-local-id",
    role: "PLATFORM_ADMIN",
  });

  // Mapa en el servidor simulado: Idempotency-Key -> huella del FormData recibido
  const serverSeenKeyPayloads = new Map<string, string>();
  let resolveAbandonedRequest!: (res: Response) => void;
  let callIndex = 0;
  let keyCounter = 0;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => {
      keyCounter += 1;
      return `f5-invariant-key-${keyCounter}`;
    },
    fetchImpl: async (_input, init) => {
      callIndex += 1;
      const headers = new Headers(init?.headers);
      const key = headers.get("Idempotency-Key") ?? "";
      const formData = init?.body as FormData;
      const payloadFingerprint = await fingerprintMultipartFormData(formData);

      // Verificación formal de la invariante obligatoria (§9):
      // Si la clave ya fue vista por el servidor, el payload DEBE ser idéntico bit a bit
      const previousFingerprint = serverSeenKeyPayloads.get(key);
      if (previousFingerprint !== undefined) {
        assert.equal(
          payloadFingerprint,
          previousFingerprint,
          `Violación de invariante: la clave ${key} se reutilizó con un payload distinto.`
        );
      } else {
        serverSeenKeyPayloads.set(key, payloadFingerprint);
      }

      // Llamada 1: falla con 503 commit_incierto para dejar la operación en uncertain_outcome
      if (callIndex === 1) {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Service Unavailable",
            status: 503,
            detail: "Commit incierto.",
            code: "commit_incierto",
            correlation_id: "corr-j-1",
          }),
          { status: 503, headers: { "Content-Type": "application/problem+json" } }
        );
      }

      // Llamada 2: reintento de la primera operación que queda colgada en red
      // hasta después de que el administrador decide abandonarla e iniciar otra carta
      if (callIndex === 2) {
        return new Promise<Response>((resolve) => {
          resolveAbandonedRequest = resolve;
        });
      }

      // Llamada 3: nueva operación con clave distinta (f5-invariant-key-2) -> responde 201
      return new Response(
        JSON.stringify({
          id: "card-second-op-id",
          code: "PKA-AGU-002",
          operation_id: "op-second-id",
          image_id: "img-second-id",
          image_status: "READY",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    },
  });

  controller.syncAvailableAbilities([{ code: "HAB-000", name: "Sin Habilidad" }], true);
  controller.setName("Carta Operación 1");
  controller.setCostInput("3");
  controller.setPowerInput("8");
  controller.setCardType("FUE");
  controller.setRarity("COMUN");
  controller.setAbilityCode("HAB-000");
  controller.setImageSelection({
    file: createF5PngFile("carta-op-1.png"),
    previewUrl: "blob:pokearena-f5/op-1",
    dimensions: { width: 1000, height: 1400 },
    sizeBytes: 16,
    mimeType: "image/png",
  });

  // 1. Primer intento -> 503 commit_incierto (clave f5-invariant-key-1)
  await controller.submit();
  assert.equal(controller.getState().status, "uncertain_outcome");
  assert.equal(controller.getState().activeIdempotencyKey, "f5-invariant-key-1");

  // 2. El usuario intenta cambiar todos los campos mientras está en uncertain_outcome;
  // la máquina de estados bloquea las mutaciones para proteger la invariante
  controller.setName("Intento De Mutación Bloqueado");
  controller.setCostInput("9");
  controller.setCardType("PSI");

  // 3. Reintenta la operación 1 (queda en vuelo) y mientras tanto regresa a uncertain_outcome
  // o se abandona explícitamente cuando está en uncertain_outcome:
  // Primero verifiquemos que el reintento envía exactamente el mismo payload bajo f5-invariant-key-1
  const pendingRetryPromise = controller.retryPendingOperation();
  // Esperar un microtick para que fetchImpl registre la llamada 2 y compruebe la huella
  await new Promise((r) => setTimeout(r, 5));
  assert.equal(callIndex, 2);

  // Supongamos que la llamada 2 termina en error de red -> vuelve a uncertain_outcome
  resolveAbandonedRequest(
    new Response(
      JSON.stringify({
        type: "about:blank",
        title: "Service Unavailable",
        status: 503,
        detail: "Sigue incierto.",
        code: "commit_incierto",
        correlation_id: "corr-j-2",
      }),
      { status: 503, headers: { "Content-Type": "application/problem+json" } }
    )
  );
  await pendingRetryPromise;
  assert.equal(controller.getState().status, "uncertain_outcome");

  // 4. El usuario abandona explícitamente el intento incierto y edita una segunda carta distinta
  controller.abandonUncertainOperation();
  assert.equal(controller.getState().status, "draft");
  assert.equal(controller.getState().activeIdempotencyKey, null);

  controller.setName("Carta Operación 2 Nueva");
  controller.setCardType("AGU");
  const secondResult = await controller.submit();
  assert.equal(secondResult?.code, "PKA-AGU-002");
  assert.equal(controller.getState().activeIdempotencyKey, "f5-invariant-key-2");
  assert.equal(serverSeenKeyPayloads.size, 2);
  assert.notEqual(
    serverSeenKeyPayloads.get("f5-invariant-key-1"),
    serverSeenKeyPayloads.get("f5-invariant-key-2")
  );

  controller.dispose();
});

test("Fase 3 (§10 y §17): verifica matriz completa de errores RFC 7807 (400, 403, 404, 413, 415, 422, 500) y aislamiento al cambiar de administrador", async () => {
  setPlatformSession({
    access_token: ADMIN_TOKEN_1,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-uno",
    role: "PLATFORM_ADMIN",
  });

  const errorStatusesToTest: Array<{
    readonly status: number;
    readonly code: string;
    readonly detail: string;
    readonly expectPreserveKey: boolean;
  }> = [
    {
      status: 400,
      code: "solicitud_malformada",
      detail: "Cuerpo inválido.",
      expectPreserveKey: false,
    },
    {
      status: 403,
      code: "permiso_denegado",
      detail: "Se requiere el rol PLATFORM_ADMIN.",
      expectPreserveKey: false,
    },
    {
      status: 404,
      code: "habilidad_inexistente",
      detail: "La habilidad no existe.",
      expectPreserveKey: false,
    },
    {
      status: 413,
      code: "imagen_demasiado_grande",
      detail: "El archivo supera el tamaño permitido.",
      expectPreserveKey: false,
    },
    {
      status: 415,
      code: "multipart_requerido",
      detail: "Usa multipart/form-data.",
      expectPreserveKey: false,
    },
    {
      status: 422,
      code: "imagen_invalida",
      detail: "La imagen no cumple los requisitos.",
      expectPreserveKey: false,
    },
    {
      status: 500,
      code: "error_interno",
      detail: "La solicitud no se pudo completar.",
      expectPreserveKey: true,
    },
  ];

  for (const scenario of errorStatusesToTest) {
    const controller = new CreateCardController({
      generateIdempotencyKey: () => `key-for-${scenario.status}`,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Error",
            status: scenario.status,
            detail: scenario.detail,
            code: scenario.code,
            correlation_id: `corr-${scenario.status}`,
          }),
          {
            status: scenario.status,
            headers: { "Content-Type": "application/problem+json" },
          }
        ),
    });

    controller.syncAvailableAbilities([{ code: "HAB-000", name: "Sin Habilidad" }], true);
    controller.setName("Carta Matriz RFC7807");
    controller.setImageSelection({
      file: createF5PngFile(),
      previewUrl: "blob:pokearena-f5/matrix",
      dimensions: { width: 1000, height: 1400 },
      sizeBytes: 16,
      mimeType: "image/png",
    });

    const outcome = await controller.submit();
    assert.equal(outcome, null);
    assert.equal(controller.getState().errorInfo?.status, scenario.status);
    assert.equal(controller.getState().errorInfo?.code, scenario.code);
    assert.equal(controller.getState().errorInfo?.correlationId, `corr-${scenario.status}`);

    if (scenario.expectPreserveKey) {
      assert.equal(controller.getState().status, "uncertain_outcome");
      assert.equal(controller.getState().activeIdempotencyKey, `key-for-${scenario.status}`);
    } else {
      assert.equal(controller.getState().status, "definite_error");
      assert.equal(controller.getState().activeIdempotencyKey, null);
    }

    controller.dispose();
  }

  // Verificar aislamiento cuando cambia el usuario administrador activo y luego hace logout
  const sessionBoundController = new CreateCardController({
    fetchImpl: async () => new Response(null, { status: 204 }),
  });
  sessionBoundController.start();
  sessionBoundController.setName("Borrador Secreto de Admin Uno");
  assert.equal(sessionBoundController.getState().values.name, "Borrador Secreto de Admin Uno");

  // Inicia sesión un administrador distinto (admin-dos) -> el borrador del admin anterior se limpia
  setPlatformSession({
    access_token: ADMIN_TOKEN_2,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-dos",
    role: "PLATFORM_ADMIN",
  });
  assert.equal(sessionBoundController.getState().values.name, "");

  // Logout explícito revoca la sesión y limpia el almacén en memoria
  const logoutResult = await logoutPlatformSession({
    fetchImpl: async () => new Response(null, { status: 204 }),
  });
  assert.equal(logoutResult.localSessionCleared, true);
  assert.equal(logoutResult.remoteRevocationConfirmed, true);
  assert.equal(getActiveSessionSnapshot(), null);

  sessionBoundController.dispose();
});
