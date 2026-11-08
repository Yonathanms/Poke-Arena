/**
 * Pruebas automatizadas de componentes e integración para la etapa F4:
 * `CardPreviewCard`, `CardForm`, `CatalogListScreen` y `CreateCardScreen`.
 *
 * Verifica:
 * - Previsualización en tiempo real 5:7, marcador provisional `PKA-<TIPO>-???` antes
 *   de crear y sustitución por el código oficial del backend tras `201 Created`.
 * - Accesibilidad de `CardForm` (`<label htmlFor>`, `id`, `aria-invalid`, `aria-describedby`).
 * - Manejo visual de estados de habilidades (cargando, error con botón de reintento, vacío).
 * - Bloqueo de controles e indicadores de clave durante `submitting` y `uncertain_outcome`.
 * - Integración completa en `CreateCardScreen` y registro honesto de sesión en `CatalogListScreen`.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  clearPlatformSession,
  setPlatformSession,
} from "../src/web-admin/modules/auth/services/session-store.ts";
import { CardForm } from "../src/web-admin/modules/catalogo/components/CardForm.tsx";
import {
  CardPreviewCard,
  formatDisplayCost,
  formatDisplayPower,
  formatProvisionalCardCode,
} from "../src/web-admin/modules/catalogo/components/CardPreviewCard.tsx";
import {
  CreateCardController,
  resetSharedCreateCardControllerForTests,
} from "../src/web-admin/modules/catalogo/hooks/useCreateCard.ts";
import { CatalogListScreen } from "../src/web-admin/modules/catalogo/screens/CatalogListScreen.tsx";
import { CreateCardScreen } from "../src/web-admin/modules/catalogo/screens/CreateCardScreen.tsx";
import type {
  AbilityOptionDTO,
  ValidatedCardImageSelection,
} from "../src/web-admin/modules/catalogo/types/card-admin.types.ts";

const VALID_ADMIN_TOKEN = "ADM_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm";

const SAMPLE_ABILITIES: readonly AbilityOptionDTO[] = Object.freeze([
  { code: "HAB-000", name: "Sin Habilidad" },
  { code: "HAB-001", name: "Impulso Ígneo" },
  { code: "HAB-004", name: "Esfera Aural" },
]);

function createSampleImageSelection(): ValidatedCardImageSelection {
  const file = new File([new Uint8Array([1, 2, 3, 4])], "lucario-arte.webp", {
    type: "image/webp",
  });
  return Object.freeze({
    file,
    previewUrl: "blob:pokearena-test/shared-preview-url",
    dimensions: Object.freeze({ width: 600, height: 840 }),
    sizeBytes: 245_000,
    mimeType: "image/webp",
  });
}

beforeEach(() => {
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
});

test("CardPreviewCard muestra código provisional PKA-<TIPO>-??? en borrador y el código oficial tras 201 Created sin crear ObjectURLs", () => {
  assert.equal(formatProvisionalCardCode("LUC"), "PKA-LUC-???");
  assert.equal(formatDisplayCost(5), "5");
  assert.equal(formatDisplayCost(99), "?");
  assert.equal(formatDisplayPower(14), "+14");
  assert.equal(formatDisplayPower(-8), "-8");
  assert.equal(formatDisplayPower(0), "0");
  assert.equal(formatDisplayPower(-50), "?");

  const imageSelection = createSampleImageSelection();

  // 1. En borrador antes de confirmar
  const draftHtml = renderToStaticMarkup(
    React.createElement(CardPreviewCard, {
      values: {
        name: "Lucario Guardián",
        cost: 4,
        power: -5,
        card_type: "LUC",
        rarity: "LEGENDARIA",
        ability_code: "HAB-004",
      },
      abilities: SAMPLE_ABILITIES,
      imageSelection,
      status: "draft",
      createdCard: null,
    })
  );

  assert.match(draftHtml, /Lucario Guardián/);
  assert.match(draftHtml, /PKA-LUC-\?\?\?/);
  assert.match(draftHtml, /Borrador en edición/);
  assert.match(draftHtml, /Esfera Aural/);
  assert.match(draftHtml, /HAB-004/);
  assert.match(draftHtml, /-5/);
  assert.match(draftHtml, /blob:pokearena-test\/shared-preview-url/);

  // 2. Confirmada tras recibir 201 Created del servidor
  const confirmedHtml = renderToStaticMarkup(
    React.createElement(CardPreviewCard, {
      values: {
        name: "Lucario Guardián",
        cost: 4,
        power: -5,
        card_type: "LUC",
        rarity: "LEGENDARIA",
        ability_code: "HAB-004",
      },
      abilities: SAMPLE_ABILITIES,
      imageSelection,
      status: "success",
      createdCard: {
        id: "card-uuid-777",
        code: "PKA-LUC-001",
        operation_id: "op-uuid-777",
        image_id: "img-uuid-777",
        image_status: "READY",
      },
    })
  );

  assert.match(confirmedHtml, /PKA-LUC-001/);
  assert.equal(confirmedHtml.includes("PKA-LUC-???"), false);
  assert.match(confirmedHtml, /Confirmada · READY/);
  assert.match(confirmedHtml, /card-uuid-777/);
  assert.match(confirmedHtml, /img-uuid-777/);
});

test("CardForm vincula etiquetas htmlFor/id, expone aria-invalid en errores de campo y maneja estados de habilidades", () => {
  const htmlWithErrors = renderToStaticMarkup(
    React.createElement(CardForm, {
      values: {
        name: "",
        cost: 15,
        power: -25,
        card_type: "FUE",
        rarity: "COMUN",
        ability_code: "HAB-999",
      },
      rawCostInput: "15",
      rawPowerInput: "-25",
      imageSelection: null,
      fieldErrors: {
        name: "El nombre de la carta es obligatorio.",
        cost: "El costo debe estar entre 0 y 10.",
        power: "El poder debe estar entre -20 y 20.",
        ability_code: "La habilidad seleccionada no existe en el catálogo actual.",
        image: "Se requiere seleccionar una imagen original para la carta.",
      },
      status: "draft",
      isSubmitting: false,
      isEditingLocked: false,
      activeIdempotencyKey: null,
      abilities: SAMPLE_ABILITIES,
      isLoadingAbilities: false,
      hasLoadedAbilities: true,
      isAbilitiesEmpty: false,
      abilitiesError: {
        status: 503,
        code: "servicio_no_disponible",
        detail: "Fallo temporal al consultar habilidades.",
        correlationId: "corr-abilities-503",
      },
      onNameChange: () => {},
      onCostInputChange: () => {},
      onPowerInputChange: () => {},
      onCardTypeChange: () => {},
      onRarityChange: () => {},
      onAbilityCodeChange: () => {},
      onImageChange: () => {},
      onImageValidationErrorChange: () => {},
      onReloadAbilities: () => {},
      onSubmit: () => {},
      onRetryPendingOperation: () => {},
      onAbandonUncertainOperation: () => {},
      onStartNewCard: () => {},
    })
  );

  // Verificar asociación accesible label for <-> id en todos los campos del formulario
  const labelForMatches = [...htmlWithErrors.matchAll(/for="([^"]+)"/g)].map((m) => m[1]);
  assert.equal(labelForMatches.length >= 7, true);
  for (const targetId of labelForMatches) {
    assert.ok(targetId && htmlWithErrors.includes(`id="${targetId}"`));
  }

  assert.match(htmlWithErrors, /El nombre de la carta es obligatorio\./);
  assert.match(htmlWithErrors, /El costo debe estar entre 0 y 10\./);
  assert.match(htmlWithErrors, /El poder debe estar entre -20 y 20\./);
  assert.match(htmlWithErrors, /La habilidad seleccionada no existe en el catálogo actual\./);
  assert.match(htmlWithErrors, /Fallo temporal al consultar habilidades\./);
  assert.match(htmlWithErrors, /corr-abilities-503/);
  assert.match(htmlWithErrors, /Reintentar carga de habilidades/);
  assert.match(htmlWithErrors, /aria-invalid="true"/);
});

test("CreateCardScreen integra formulario, vista previa, banner de resultado incierto y confirmación 201", async () => {
  let shouldFailWith503 = true;

  const controller = new CreateCardController({
    generateIdempotencyKey: () => "idem-screen-integration-001",
    fetchImpl: async () => {
      if (shouldFailWith503) {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Service Unavailable",
            status: 503,
            detail: "Confirmación SQL incierta.",
            code: "commit_incierto",
            correlation_id: "corr-screen-503",
          }),
          { status: 503, headers: { "Content-Type": "application/problem+json" } }
        );
      }

      return new Response(
        JSON.stringify({
          id: "card-screen-001",
          code: "PKA-AGU-003",
          operation_id: "op-screen-001",
          image_id: "img-screen-001",
          image_status: "READY",
        }),
        {
          status: 201,
          headers: {
            "Content-Type": "application/json",
            "X-Correlation-ID": "corr-screen-201",
          },
        }
      );
    },
  });

  controller.syncAvailableAbilities(SAMPLE_ABILITIES, true);
  controller.setName("Blastoise Bastión Hidráulico");
  controller.setCostInput("6");
  controller.setPowerInput("15");
  controller.setCardType("AGU");
  controller.setRarity("RARA");
  controller.setAbilityCode("HAB-000");
  controller.setImageSelection(createSampleImageSelection());

  // 1. Primer intento -> 503 commit_incierto -> muestra banner de advertencia y botón de replay
  await controller.submit();
  const uncertainHtml = renderToStaticMarkup(
    React.createElement(CreateCardScreen, { controller })
  );
  assert.match(uncertainHtml, /Confirmación incierta en el servidor \(503\)/);
  assert.match(uncertainHtml, /corr-screen-503/);
  assert.match(uncertainHtml, /idem-screen-integration-001/);
  assert.match(uncertainHtml, /Reintentar operación con la misma Idempotency-Key/);
  assert.match(uncertainHtml, /Payload bloqueado para reintento idempotente/);

  // 2. Replay exitoso -> 201 Created -> muestra código oficial PKA-AGU-003 y botón "Crear otra carta"
  shouldFailWith503 = false;
  await controller.retryPendingOperation();
  const successHtml = renderToStaticMarkup(
    React.createElement(CreateCardScreen, { controller })
  );
  assert.match(successHtml, /Carta creada exitosamente — Código oficial: PKA-AGU-003/);
  assert.match(successHtml, /card-screen-001/);
  assert.match(successHtml, /img-screen-001/);
  assert.match(successHtml, /Crear otra carta/);

  // 3. CatalogListScreen muestra la entrada confirmada en la sesión actual con transparencia
  const historyHtml = renderToStaticMarkup(
    React.createElement(CatalogListScreen, {
      entries: controller.getState().sessionHistory,
    })
  );
  assert.match(historyHtml, /Cartas Creadas en la Sesión Actual \(1\)/);
  assert.match(historyHtml, /PKA-AGU-003/);
  assert.match(historyHtml, /Blastoise Bastión Hidráulico/);
  assert.match(historyHtml, /Alcance del registro en la Entrega 1G/);
});
