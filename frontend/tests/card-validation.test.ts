/**
 * Pruebas unitarias de `card-validation.ts` (nombre, costo, poder, tipos, rarezas,
 * habilidad, archivo de imagen de hasta 5 000 000 bytes, resolución mínima 600×840
 * y proporción exacta 5:7).
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CARD_RARITIES,
  CARD_TYPES,
  hasExactCardAspectRatio,
  isValidIdempotencyKey,
  validateAbilityCode,
  validateCardCost,
  validateCardName,
  validateCardPower,
  validateCardRarity,
  validateCardType,
  validateCreateCardForm,
  validateImageDimensions,
  validateImageFileMetadata,
} from "../src/web-admin/modules/catalogo/validation/card-validation.ts";

test("valida y recorta el nombre de la carta entre 1 y 100 caracteres sin nulos", () => {
  assert.equal(validateCardName("  Guardiana Solar  "), null);
  assert.equal(validateCardName("A".repeat(100)), null);
  assert.ok(validateCardName("   ") !== null);
  assert.ok(validateCardName("A".repeat(101)) !== null);
  assert.ok(validateCardName("Carta\0Trampa") !== null);
});

test("valida los límites exactos de costo (0..10) y poder (-20..20)", () => {
  assert.equal(validateCardCost(0), null);
  assert.equal(validateCardCost(10), null);
  assert.ok(validateCardCost(-1) !== null);
  assert.ok(validateCardCost(11) !== null);
  assert.ok(validateCardCost(2.5) !== null);

  assert.equal(validateCardPower(-20), null);
  assert.equal(validateCardPower(0), null);
  assert.equal(validateCardPower(20), null);
  assert.ok(validateCardPower(-21) !== null);
  assert.ok(validateCardPower(21) !== null);
  assert.ok(validateCardPower(1.2) !== null);
});

test("acepta únicamente los 6 tipos elementales y las 4 rarezas canónicas", () => {
  assert.deepEqual(CARD_TYPES, ["FUE", "AGU", "PLA", "ELE", "PSI", "LUC"]);
  for (const cardType of CARD_TYPES) {
    assert.equal(validateCardType(cardType), null);
  }
  assert.ok(validateCardType("INC") !== null);
  assert.ok(validateCardType("DRG") !== null);

  assert.deepEqual(CARD_RARITIES, ["COMUN", "POCO_COMUN", "RARA", "LEGENDARIA"]);
  for (const rarity of CARD_RARITIES) {
    assert.equal(validateCardRarity(rarity), null);
  }
  assert.ok(validateCardRarity("EPICA") !== null);
});

test("valida el código de habilidad contra el patrón HAB-NNN y la lista del catálogo", () => {
  assert.equal(validateAbilityCode("HAB-000", ["HAB-000", "HAB-001"]), null);
  assert.ok(validateAbilityCode("", ["HAB-000"]) !== null);
  assert.ok(validateAbilityCode("HAB-12", ["HAB-000"]) !== null);
  assert.ok(validateAbilityCode("HAB-999", ["HAB-000", "HAB-001"]) !== null);
});

test("valida formato MIME (PNG/JPEG/WebP) y límite estricto de 5 000 000 bytes", () => {
  assert.equal(
    validateImageFileMetadata({ mimeType: "image/png", sizeBytes: 5_000_000 }),
    null
  );
  assert.equal(
    validateImageFileMetadata({ mimeType: "image/jpeg", sizeBytes: 120_000 }),
    null
  );
  assert.equal(
    validateImageFileMetadata({ mimeType: "image/webp", sizeBytes: 1 }),
    null
  );

  // 5 000 001 bytes se rechaza aunque sea menor que 5 MiB (5 242 880)
  assert.ok(
    validateImageFileMetadata({ mimeType: "image/png", sizeBytes: 5_000_001 }) !== null
  );
  assert.ok(
    validateImageFileMetadata({ mimeType: "image/png", sizeBytes: 0 }) !== null
  );
  assert.ok(
    validateImageFileMetadata({ mimeType: "image/gif", sizeBytes: 1024 }) !== null
  );
  assert.ok(validateImageFileMetadata(null) !== null);
});

test("valida resolución mínima 600×840, proporción exacta 5:7 y techo de 20 MP", () => {
  assert.equal(hasExactCardAspectRatio({ width: 600, height: 840 }), true);
  assert.equal(hasExactCardAspectRatio({ width: 1000, height: 1400 }), true);
  assert.equal(validateImageDimensions({ width: 600, height: 840 }), null);
  assert.equal(validateImageDimensions({ width: 1500, height: 2100 }), null);

  // Proporción 5:7 pero menor a 600×840
  assert.ok(validateImageDimensions({ width: 500, height: 700 }) !== null);
  // Resolución suficiente pero proporción no exacta (601×840)
  assert.ok(validateImageDimensions({ width: 601, height: 840 }) !== null);
  // Excede los 20 000 000 de píxeles aunque sea 5:7 (4000 × 5600 = 22 400 000)
  assert.ok(validateImageDimensions({ width: 4000, height: 5600 }) !== null);
});

test("valida el formulario completo y devuelve valores normalizados listos para enviar", () => {
  const validResult = validateCreateCardForm(
    {
      name: "  Guardiana  ",
      cost: 2,
      power: -5,
      card_type: "LUC",
      rarity: "RARA",
      ability_code: "HAB-000",
    },
    {
      availableAbilityCodes: ["HAB-000", "HAB-001"],
      imageCandidate: { mimeType: "image/png", sizeBytes: 250_000 },
      imageDimensions: { width: 600, height: 840 },
    }
  );

  assert.equal(validResult.valid, true);
  assert.deepEqual(validResult.errors, {});
  assert.deepEqual(validResult.normalizedValues, {
    name: "Guardiana",
    cost: 2,
    power: -5,
    card_type: "LUC",
    rarity: "RARA",
    ability_code: "HAB-000",
  });

  const invalidResult = validateCreateCardForm(
    {
      name: "   ",
      cost: 15,
      power: -25,
      card_type: "FUE",
      rarity: "COMUN",
      ability_code: "HAB-404",
    },
    {
      availableAbilityCodes: ["HAB-000"],
      imageCandidate: { mimeType: "image/png", sizeBytes: 5_100_000 },
      imageDimensions: { width: 600, height: 840 },
    }
  );

  assert.equal(invalidResult.valid, false);
  assert.ok(invalidResult.errors.name);
  assert.ok(invalidResult.errors.cost);
  assert.ok(invalidResult.errors.power);
  assert.ok(invalidResult.errors.ability_code);
  assert.ok(invalidResult.errors.image);
});

test("valida el patrón de Idempotency-Key del backend", () => {
  assert.equal(isValidIdempotencyKey("550e8400-e29b-41d4-a716-446655440000"), true);
  assert.equal(isValidIdempotencyKey(""), false);
  assert.equal(isValidIdempotencyKey("con espacio"), false);
  assert.equal(isValidIdempotencyKey("con,coma"), false);
  assert.equal(isValidIdempotencyKey("x".repeat(129)), false);
});
