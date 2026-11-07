/**
 * Pruebas unitarias exhaustivas de `useCreateCard.ts` (`CreateCardController`):
 * cubre los 14 escenarios obligatorios de idempotencia (§9.8), la máquina de
 * estados finita, la congelación inmutable del payload multipart y la
 * preservación del borrador ante expiración de sesión (`401`).
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import {
  clearPlatformSession,
  configureSessionClockForTests,
  setPlatformSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";
import {
  CreateCardController,
  parseUnclampedNumericInput,
  resetSharedCreateCardControllerForTests,
} from "../src/web-admin/modules/catalogo/hooks/useCreateCard.ts";
import type {
  AbilityOptionDTO,
  ValidatedCardImageSelection,
} from "../src/web-admin/modules/catalogo/types/card-admin.types.ts";

const VALID_ADMIN_TOKEN = "ADM_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm";
const RENEWED_ADMIN_TOKEN = "ADM_ZYXWVUTSRQPONMLKJIHGFEDCBA9876543210abc";

const MOCK_ABILITIES: readonly AbilityOptionDTO[] = Object.freeze([
  { code: "HAB-000", name: "Sin Habilidad" },
  { code: "HAB-001", name: "Impulso Ígneo" },
  { code: "HAB-004", name: "Esfera Aural" },
]);

function createMockValidImageSelection(fileName = "lucario-5x7.png"): ValidatedCardImageSelection {
  const bytes = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
  const file = new File([bytes], fileName, { type: "image/png" });
  return Object.freeze({
    file,
    previewUrl: "blob:pokearena-test/lucario-preview-1",
    dimensions: Object.freeze({ width: 600, height: 840 }),
    sizeBytes: file.size,
    mimeType: "image/png",
  });
}

function populateValidDraft(controller: CreateCardController): void {
  controller.syncAvailableAbilities(MOCK_ABILITIES, true);
  controller.setName("  Lucario Guardián del Aura  ");
  controller.setCostInput("4");
  controller.setPowerInput("12");
  controller.setCardType("LUC");
  controller.setRarity("LEGENDARIA");
  controller.setAbilityCode("HAB-004");
  controller.setImageSelection(createMockValidImageSelection());
}

let simulatedNowMs = 1_700_000_000_000;

beforeEach(() => {
  simulatedNowMs = 1_700_000_000_000;
  configureSessionClockForTests(() => simulatedNowMs);
  clearPlatformSession("manual_logout");
  resetSharedCreateCardControllerForTests();
  setPlatformSession({
    access_token: VALID_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-maestro-01",
    role: "PLATFORM_ADMIN",
  });
});

afterEach(() => {
  resetSharedCreateCardControllerForTests();
  clearPlatformSession("manual_logout");
  configureSessionClockForTests();
});

test("Escenario 1 y 2: no genera Idempotency-Key si la validación local falla, y genera exactamente una al enviar un formulario válido", async () => {
  let generatedCount = 0;
  let fetchCount = 0;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => {
      generatedCount += 1;
      return `idem-key-00${generatedCount}`;
    },
    fetchImpl: async (_input, init) => {
      fetchCount += 1;
      const headers = new Headers(init?.headers);
      assert.equal(headers.get("Idempotency-Key"), "idem-key-001");
      assert.equal(headers.get("Authorization"), `Bearer ${VALID_ADMIN_TOKEN}`);
      return new Response(
        JSON.stringify({
          id: "card-uuid-001",
          code: "PKA-LUC-001",
          operation_id: "op-uuid-001",
          image_id: "img-uuid-001",
          image_status: "READY",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    },
  });

  // Intento 1: formulario vacío/inválido -> NO genera clave ni llama a fetch
  const invalidResult = await controller.submit();
  assert.equal(invalidResult, null);
  assert.equal(generatedCount, 0);
  assert.equal(fetchCount, 0);
  assert.equal(controller.getState().activeIdempotencyKey, null);
  assert.ok(controller.getState().fieldErrors.name);
  assert.ok(controller.getState().fieldErrors.image);

  // Intento 2: formulario completo y válido -> genera idem-key-001 y recibe 201
  populateValidDraft(controller);
  const validResult = await controller.submit();
  assert.equal(generatedCount, 1);
  assert.equal(fetchCount, 1);
  assert.equal(validResult?.code, "PKA-LUC-001");
  assert.equal(controller.getState().status, "success");
  assert.equal(controller.getState().activeIdempotencyKey, "idem-key-001");
});

test("Escenario 3: doble clic rápido envía una sola solicitud HTTP y no rota la clave", async () => {
  let generatedCount = 0;
  let fetchCount = 0;
  let resolveServer!: (res: Response) => void;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => {
      generatedCount += 1;
      return `idem-double-click-${generatedCount}`;
    },
    fetchImpl: () => {
      fetchCount += 1;
      return new Promise<Response>((resolve) => {
        resolveServer = resolve;
      });
    },
  });

  populateValidDraft(controller);

  const firstAttempt = controller.submit();
  const secondAttempt = controller.submit();

  assert.equal(generatedCount, 1);
  assert.equal(fetchCount, 1);
  assert.equal(controller.getState().status, "submitting");

  resolveServer(
    new Response(
      JSON.stringify({
        id: "card-uuid-002",
        code: "PKA-LUC-002",
        operation_id: "op-uuid-002",
        image_id: "img-uuid-002",
        image_status: "READY",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } }
    )
  );

  const [res1, res2] = await Promise.all([firstAttempt, secondAttempt]);
  assert.deepEqual(res1, res2);
  assert.equal(res1?.code, "PKA-LUC-002");
  assert.equal(fetchCount, 1);
});

test("Escenarios 4, 5, 6, 7, 8 y 9: error de red, 500, 503 commit_incierto y 409 en_curso conservan la misma Idempotency-Key y payload congelado hasta lograr 201 en el replay", async () => {
  const seenIdempotencyKeys: string[] = [];
  const seenNames: string[] = [];
  let attemptIndex = 0;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => "idem-uncertain-sequence-uuid",
    fetchImpl: async (_input, init) => {
      attemptIndex += 1;
      const headers = new Headers(init?.headers);
      seenIdempotencyKeys.push(headers.get("Idempotency-Key") ?? "");
      const body = init?.body as FormData;
      seenNames.push(String(body.get("name")));

      // Intento 1: Fallo de red (Escenario 4)
      if (attemptIndex === 1) {
        throw new TypeError("Failed to fetch");
      }
      // Intento 2: 500 Internal Server Error (Escenario 5)
      if (attemptIndex === 2) {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Internal Server Error",
            status: 500,
            detail: "Fallo inesperado.",
            code: "error_interno",
            correlation_id: "corr-500",
          }),
          { status: 500, headers: { "Content-Type": "application/problem+json" } }
        );
      }
      // Intento 3: 503 commit_incierto (Escenario 6)
      if (attemptIndex === 3) {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Service Unavailable",
            status: 503,
            detail: "No se pudo confirmar el commit SQL.",
            code: "commit_incierto",
            correlation_id: "corr-503",
          }),
          { status: 503, headers: { "Content-Type": "application/problem+json" } }
        );
      }
      // Intento 4: 409 en_curso (Escenario 7)
      if (attemptIndex === 4) {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Conflict",
            status: 409,
            detail: "La operación sigue en progreso.",
            code: "en_curso",
            correlation_id: "corr-409-in-progress",
          }),
          { status: 409, headers: { "Content-Type": "application/problem+json" } }
        );
      }
      // Intento 5: Replay exitoso 201 Created (Escenarios 8 y 9)
      return new Response(
        JSON.stringify({
          id: "card-recovered-001",
          code: "PKA-LUC-007",
          operation_id: "op-recovered-001",
          image_id: "img-recovered-001",
          image_status: "READY",
        }),
        {
          status: 201,
          headers: {
            "Content-Type": "application/json",
            "X-Correlation-ID": "corr-201-replay",
          },
        }
      );
    },
  });

  populateValidDraft(controller);

  // 1. Fallo de red -> uncertain_outcome
  assert.equal(await controller.submit(), null);
  assert.equal(controller.getState().status, "uncertain_outcome");
  assert.equal(controller.getState().activeIdempotencyKey, "idem-uncertain-sequence-uuid");
  assert.equal(controller.getState().errorInfo?.isNetworkError, true);

  // Intentar modificar el nombre mientras está bloqueado en uncertain_outcome no debe mutar el snapshot
  controller.setName("Nombre Alterado Que Debe Ignorarse");
  assert.equal(controller.getState().values.name, "Lucario Guardián del Aura");

  // 2. Reintento -> 500 -> sigue en uncertain_outcome con misma clave
  assert.equal(await controller.retryPendingOperation(), null);
  assert.equal(controller.getState().status, "uncertain_outcome");
  assert.equal(controller.getState().errorInfo?.status, 500);
  assert.equal(controller.getState().errorInfo?.correlationId, "corr-500");

  // 3. Reintento -> 503 commit_incierto -> sigue en uncertain_outcome con misma clave
  assert.equal(await controller.retryPendingOperation(), null);
  assert.equal(controller.getState().status, "uncertain_outcome");
  assert.equal(controller.getState().errorInfo?.code, "commit_incierto");

  // 4. Reintento -> 409 en_curso -> sigue en uncertain_outcome con misma clave
  assert.equal(await controller.retryPendingOperation(), null);
  assert.equal(controller.getState().status, "uncertain_outcome");
  assert.equal(controller.getState().errorInfo?.code, "en_curso");

  // 5. Reintento -> 201 Created -> recupera la carta creada sin duplicar en sessionHistory
  const recovered = await controller.retryPendingOperation();
  assert.equal(recovered?.code, "PKA-LUC-007");
  assert.equal(controller.getState().status, "success");
  assert.equal(controller.getState().sessionHistory.length, 1);

  // Todos los 5 envíos usaron exactamente la misma clave y el mismo nombre normalizado
  assert.deepEqual(seenIdempotencyKeys, [
    "idem-uncertain-sequence-uuid",
    "idem-uncertain-sequence-uuid",
    "idem-uncertain-sequence-uuid",
    "idem-uncertain-sequence-uuid",
    "idem-uncertain-sequence-uuid",
  ]);
  assert.deepEqual(seenNames, [
    "Lucario Guardián del Aura",
    "Lucario Guardián del Aura",
    "Lucario Guardián del Aura",
    "Lucario Guardián del Aura",
    "Lucario Guardián del Aura",
  ]);
});

test("Escenario 10: 409 conflicto_idempotencia NO reintenta automáticamente y libera la clave en conflicto", async () => {
  let fetchCount = 0;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => `idem-conflict-${fetchCount + 1}`,
    fetchImpl: async () => {
      fetchCount += 1;
      return new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Conflict",
          status: 409,
          detail: "La clave ya se utilizó con otro payload.",
          code: "conflicto_idempotencia",
          correlation_id: "corr-409-conflict",
        }),
        { status: 409, headers: { "Content-Type": "application/problem+json" } }
      );
    },
  });

  populateValidDraft(controller);
  const res = await controller.submit();

  assert.equal(res, null);
  assert.equal(fetchCount, 1);
  assert.equal(controller.getState().status, "definite_error");
  assert.equal(controller.getState().activeIdempotencyKey, null);
  assert.equal(controller.getState().frozenOperation, null);
  assert.equal(controller.getState().errorInfo?.code, "conflicto_idempotencia");
});

test("Escenarios 11 y 13: error definitivo 422 permite corregir el formulario y el siguiente envío genera una NUEVA Idempotency-Key", async () => {
  const usedKeys: string[] = [];
  let keyCounter = 0;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => {
      keyCounter += 1;
      return `idem-422-flow-${keyCounter}`;
    },
    fetchImpl: async (_input, init) => {
      const headers = new Headers(init?.headers);
      const key = headers.get("Idempotency-Key") ?? "";
      usedKeys.push(key);

      if (usedKeys.length === 1) {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Unprocessable Entity",
            status: 422,
            detail: "La habilidad seleccionada fue desactivada.",
            code: "habilidad_inexistente",
            correlation_id: "corr-422-hab",
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } }
        );
      }

      return new Response(
        JSON.stringify({
          id: "card-after-fix-001",
          code: "PKA-LUC-009",
          operation_id: "op-after-fix-001",
          image_id: "img-after-fix-001",
          image_status: "READY",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    },
  });

  populateValidDraft(controller);

  // Primer envío -> recibe 422
  assert.equal(await controller.submit(), null);
  assert.equal(controller.getState().status, "definite_error");
  assert.equal(controller.getState().activeIdempotencyKey, null);
  assert.equal(controller.getState().fieldErrors.ability_code, "La habilidad seleccionada fue desactivada.");

  // El administrador corrige la habilidad -> vuelve a draft sin clave residual
  controller.setAbilityCode("HAB-000");
  assert.equal(controller.getState().status, "draft");
  assert.equal(controller.getState().activeIdempotencyKey, null);

  // Segundo envío -> genera una NUEVA clave (idem-422-flow-2) y triunfa con 201
  const created = await controller.submit();
  assert.equal(created?.code, "PKA-LUC-009");
  assert.deepEqual(usedKeys, ["idem-422-flow-1", "idem-422-flow-2"]);
});

test("Escenario 12: después de 201 Created, startNewCard() reinicia el formulario y la siguiente carta usa una nueva Idempotency-Key", async () => {
  const usedKeys: string[] = [];
  let keyCounter = 0;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => {
      keyCounter += 1;
      return `idem-card-seq-${keyCounter}`;
    },
    fetchImpl: async (_input, init) => {
      const headers = new Headers(init?.headers);
      const key = headers.get("Idempotency-Key") ?? "";
      usedKeys.push(key);
      return new Response(
        JSON.stringify({
          id: `card-id-${usedKeys.length}`,
          code: `PKA-LUC-00${usedKeys.length}`,
          operation_id: `op-id-${usedKeys.length}`,
          image_id: `img-id-${usedKeys.length}`,
          image_status: "READY",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    },
  });

  populateValidDraft(controller);
  const first = await controller.submit();
  assert.equal(first?.code, "PKA-LUC-001");
  assert.equal(controller.getState().status, "success");

  // Mientras está en success, llamar submit() de nuevo NO vuelve a enviar la solicitud
  await controller.submit();
  assert.equal(usedKeys.length, 1);

  // Al iniciar una nueva carta, se limpia el formulario y la clave activa
  controller.startNewCard();
  assert.equal(controller.getState().status, "draft");
  assert.equal(controller.getState().activeIdempotencyKey, null);
  assert.equal(controller.getState().createdCard, null);
  assert.equal(controller.getState().values.name, "");
  assert.equal(controller.getState().sessionHistory.length, 1);

  // Llenar segunda carta y enviar -> usa idem-card-seq-2
  populateValidDraft(controller);
  controller.setName("Gardevoir Oráculo Astral");
  controller.setCardType("PSI");
  const second = await controller.submit();
  assert.equal(second?.code, "PKA-LUC-002");
  assert.deepEqual(usedKeys, ["idem-card-seq-1", "idem-card-seq-2"]);
  assert.equal(controller.getState().sessionHistory.length, 2);
});

test("Escenario 14: expiración de sesión o 401 conserva el borrador y la Idempotency-Key para reanudar tras reautenticación, mientras manual_logout limpia todo", async () => {
  const usedKeys: string[] = [];
  const usedTokens: string[] = [];
  let shouldReturn401 = true;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => "idem-preserved-across-401",
    fetchImpl: async (_input, init) => {
      const headers = new Headers(init?.headers);
      usedKeys.push(headers.get("Idempotency-Key") ?? "");
      usedTokens.push(headers.get("Authorization") ?? "");

      if (shouldReturn401) {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Unauthorized",
            status: 401,
            detail: "La sesión ha expirado.",
            code: "no_autenticado",
            correlation_id: "corr-401-expired",
          }),
          { status: 401, headers: { "Content-Type": "application/problem+json" } }
        );
      }

      return new Response(
        JSON.stringify({
          id: "card-after-reauth",
          code: "PKA-LUC-014",
          operation_id: "op-after-reauth",
          image_id: "img-after-reauth",
          image_status: "READY",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    },
  });
  controller.start();

  populateValidDraft(controller);

  // 1. El envío recibe 401 -> la sesión se invalida pero el borrador y la clave se conservan
  assert.equal(await controller.submit(), null);
  assert.equal(controller.getState().status, "uncertain_outcome");
  assert.equal(controller.getState().activeIdempotencyKey, "idem-preserved-across-401");
  assert.equal(controller.getState().values.name, "Lucario Guardián del Aura");
  assert.equal(controller.getState().errorInfo?.isSessionExpired, true);

  // 2. El mismo administrador vuelve a iniciar sesión -> conserva borrador y clave pendiente
  shouldReturn401 = false;
  setPlatformSession({
    access_token: RENEWED_ADMIN_TOKEN,
    token_type: "Bearer",
    expires_in: 900,
    user_id: "admin-maestro-01",
    role: "PLATFORM_ADMIN",
  });
  assert.equal(controller.getState().errorInfo?.isSessionExpired, false);
  assert.equal(controller.getState().activeIdempotencyKey, "idem-preserved-across-401");

  // 3. Reintenta con el nuevo token pero exactamente la misma Idempotency-Key
  const created = await controller.retryPendingOperation();
  assert.equal(created?.code, "PKA-LUC-014");
  assert.deepEqual(usedKeys, ["idem-preserved-across-401", "idem-preserved-across-401"]);
  assert.deepEqual(usedTokens, [
    `Bearer ${VALID_ADMIN_TOKEN}`,
    `Bearer ${RENEWED_ADMIN_TOKEN}`,
  ]);

  // 4. Cuando el administrador cierra sesión manualmente, todo el estado e historial se limpian
  clearPlatformSession("manual_logout");
  assert.equal(controller.getState().status, "draft");
  assert.equal(controller.getState().values.name, "");
  assert.equal(controller.getState().sessionHistory.length, 0);
  controller.dispose();
});

test("valida entradas numéricas sin recortarlas silenciosamente e invalida habilidad si desaparece tras recargar catálogo", () => {
  assert.equal(parseUnclampedNumericInput("15"), 15);
  assert.equal(parseUnclampedNumericInput("-25"), -25);
  assert.equal(Number.isNaN(parseUnclampedNumericInput("")), true);
  assert.equal(Number.isNaN(parseUnclampedNumericInput("-")), true);

  const controller = new CreateCardController();
  controller.syncAvailableAbilities(MOCK_ABILITIES, true);

  // Ingresar costo 15 y poder -25 no los recorta a 10 ni -20, sino que expone el error
  controller.setCostInput("15");
  controller.setPowerInput("-25");
  assert.equal(controller.getState().values.cost, 15);
  assert.equal(controller.getState().values.power, -25);
  assert.match(controller.getState().fieldErrors.cost ?? "", /entre 0 y 10/);
  assert.match(controller.getState().fieldErrors.power ?? "", /entre -20 y 20/);

  // Si el usuario seleccionó HAB-004 y tras recargar el catálogo ya no existe HAB-004, se marca inválida
  controller.setAbilityCode("HAB-004");
  assert.equal(controller.getState().fieldErrors.ability_code, undefined);
  controller.syncAvailableAbilities([{ code: "HAB-000", name: "Sin Habilidad" }], true);
  assert.match(
    controller.getState().fieldErrors.ability_code ?? "",
    /no existe en el catálogo actual/
  );
});
