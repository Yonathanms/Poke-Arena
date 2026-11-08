/**
 * Pruebas de `CardImageUploader.tsx` y `SequentialImageSelectionPipeline` (Etapa F3).
 *
 * Verifica:
 * 1. PNG, JPEG y WebP válidos con proporción 5:7 y resolución >= 600×840.
 * 2. Rechazo de MIME no permitido, archivo vacío (0 B) y archivo de 5 000 001 B.
 * 3. Rechazo de dimensiones menores a 600×840, proporción distinta de 5:7 y exceso de 20 MP.
 * 4. Fallo de decodificación con revocación inmediata del `objectUrl`.
 * 5. Concurrencia: si el usuario selecciona imagen A y, antes de que termine su decodificación,
 *    selecciona imagen B, A se cancela, su `objectUrl` se revoca y prevalece únicamente B.
 * 6. Reemplazo y eliminación liberando cada `objectUrl` sin fugas de memoria.
 * 7. Renderizado accesible de `CardImageUploader` en estado vacío y con vista previa 5:7.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  CardImageUploader,
  formatImageByteSize,
} from "../src/web-admin/modules/catalogo/components/CardImageUploader.tsx";
import {
  SequentialImageSelectionPipeline,
  type ImageDimensionsDecoder,
  type ObjectUrlManager,
} from "../src/web-admin/modules/catalogo/validation/card-validation.ts";

function createFakeFile(sizeBytes: number, mimeType: string, name = "carta.png"): File {
  const content = new Uint8Array(sizeBytes);
  return new File([content], name, { type: mimeType });
}

function createTrackingUrlManager(): {
  readonly manager: ObjectUrlManager;
  readonly createdUrls: string[];
  readonly revokedUrls: string[];
  readonly activeUrls: Set<string>;
} {
  let counter = 0;
  const createdUrls: string[] = [];
  const revokedUrls: string[] = [];
  const activeUrls = new Set<string>();

  const manager: ObjectUrlManager = {
    createObjectURL: () => {
      counter += 1;
      const url = `blob:pokearena-test/${counter}`;
      createdUrls.push(url);
      activeUrls.add(url);
      return url;
    },
    revokeObjectURL: (url: string) => {
      revokedUrls.push(url);
      activeUrls.delete(url);
    },
  };

  return { manager, createdUrls, revokedUrls, activeUrls };
}

test("acepta PNG, JPEG y WebP válidos (600×840, 1000×1400, 750×1050) y revoca la preview previa al reemplazar", async () => {
  const tracker = createTrackingUrlManager();
  const dimensionsByMime: Record<string, { width: number; height: number }> = {
    "image/png": { width: 600, height: 840 },
    "image/jpeg": { width: 1000, height: 1400 },
    "image/webp": { width: 750, height: 1050 },
  };

  const pipeline = new SequentialImageSelectionPipeline({
    urlManager: tracker.manager,
    decodeDimensions: async (file) => dimensionsByMime[file.type] ?? { width: 600, height: 840 },
  });

  // 1. PNG válido (5 000 000 bytes exactos)
  const pngOutcome = await pipeline.inspectFile(
    createFakeFile(5_000_000, "image/png", "fuego.png")
  );
  assert.equal(pngOutcome.status, "valid");
  assert.equal(tracker.activeUrls.size, 1);

  // 2. Reemplazar por JPEG válido -> revoca automáticamente la URL del PNG anterior
  const jpegOutcome = await pipeline.inspectFile(
    createFakeFile(250_000, "image/jpeg", "agua.jpg")
  );
  assert.equal(jpegOutcome.status, "valid");
  assert.equal(tracker.activeUrls.size, 1);
  assert.equal(tracker.revokedUrls.length, 1);

  // 3. Reemplazar por WebP válido -> revoca la URL del JPEG
  const webpOutcome = await pipeline.inspectFile(
    createFakeFile(180_000, "image/webp", "planta.webp")
  );
  assert.equal(webpOutcome.status, "valid");
  assert.equal(tracker.activeUrls.size, 1);
  assert.equal(tracker.revokedUrls.length, 2);

  // 4. Eliminar selección -> revoca la URL activa quedando 0 URLs en memoria
  pipeline.clearActiveSelection();
  assert.equal(tracker.activeUrls.size, 0);
  assert.equal(tracker.revokedUrls.length, 3);
});

test("rechaza MIME inválido, archivo vacío y archivo de 5 000 001 bytes sin crear Object URLs", async () => {
  const tracker = createTrackingUrlManager();
  const pipeline = new SequentialImageSelectionPipeline({
    urlManager: tracker.manager,
    decodeDimensions: async () => ({ width: 600, height: 840 }),
  });

  const gifOutcome = await pipeline.inspectFile(
    createFakeFile(1024, "image/gif", "animada.gif")
  );
  assert.equal(gifOutcome.status, "invalid");

  const emptyOutcome = await pipeline.inspectFile(createFakeFile(0, "image/png", "vacia.png"));
  assert.equal(emptyOutcome.status, "invalid");

  const oversizedOutcome = await pipeline.inspectFile(
    createFakeFile(5_000_001, "image/png", "excesiva.png")
  );
  assert.equal(oversizedOutcome.status, "invalid");

  // Ninguno de los archivos inválidos por metadatos debió dejar ni crear Object URLs
  assert.equal(tracker.createdUrls.length, 0);
  assert.equal(tracker.activeUrls.size, 0);
});

test("rechaza dimensiones < 600×840, proporción distinta de 5:7, > 20 MP o fallo de decodificación revocando el Object URL", async () => {
  const tracker = createTrackingUrlManager();
  let nextResult: { width: number; height: number } | "throw" = { width: 600, height: 800 };

  const decoder: ImageDimensionsDecoder = async () => {
    if (nextResult === "throw") {
      throw new Error("Corrupted image binary");
    }
    return nextResult;
  };

  const pipeline = new SequentialImageSelectionPipeline({
    urlManager: tracker.manager,
    decodeDimensions: decoder,
  });

  // 600 × 800 (proporción inválida)
  const badRatio = await pipeline.inspectFile(createFakeFile(10_000, "image/png"));
  assert.equal(badRatio.status, "invalid");
  assert.equal(tracker.activeUrls.size, 0);

  // 500 × 700 (5:7 pero menor al mínimo 600×840)
  nextResult = { width: 500, height: 700 };
  const tooSmall = await pipeline.inspectFile(createFakeFile(10_000, "image/png"));
  assert.equal(tooSmall.status, "invalid");
  assert.equal(tracker.activeUrls.size, 0);

  // 4000 × 5600 (5:7 pero 22.4 MP > 20 MP)
  nextResult = { width: 4000, height: 5600 };
  const tooManyPixels = await pipeline.inspectFile(createFakeFile(10_000, "image/png"));
  assert.equal(tooManyPixels.status, "invalid");
  assert.equal(tracker.activeUrls.size, 0);

  // Fallo de decodificación
  nextResult = "throw";
  const decodeError = await pipeline.inspectFile(createFakeFile(10_000, "image/png"));
  assert.equal(decodeError.status, "invalid");
  assert.equal(tracker.activeUrls.size, 0);
  assert.equal(tracker.createdUrls.length, 4);
  assert.equal(tracker.revokedUrls.length, 4);
});

test("protege contra condiciones de carrera cuando se selecciona una imagen B antes de que termine de decodificar la imagen A", async () => {
  const tracker = createTrackingUrlManager();
  let resolveSlowImageA: ((dims: { width: number; height: number }) => void) | null = null;
  let callOrder = 0;

  const pipeline = new SequentialImageSelectionPipeline({
    urlManager: tracker.manager,
    decodeDimensions: async () => {
      callOrder += 1;
      if (callOrder === 1) {
        return new Promise<{ width: number; height: number }>((resolve) => {
          resolveSlowImageA = resolve;
        });
      }
      return { width: 1000, height: 1400 };
    },
  });

  const fileA = createFakeFile(100_000, "image/png", "imagen-A.png");
  const fileB = createFakeFile(200_000, "image/webp", "imagen-B.webp");

  // Inicia la inspección de A (queda pendiente decodificando)
  const promiseA = pipeline.inspectFile(fileA);

  // Inmediatamente el usuario selecciona B (termina rápido)
  const outcomeB = await pipeline.inspectFile(fileB);
  assert.equal(outcomeB.status, "valid");
  if (outcomeB.status === "valid") {
    assert.deepEqual(outcomeB.dimensions, { width: 1000, height: 1400 });
  }

  // Ahora termina tardíamente la decodificación de A -> debe cancelarse y revocar su URL
  assert.ok(resolveSlowImageA !== null);
  (resolveSlowImageA as (dims: { width: number; height: number }) => void)({
    width: 600,
    height: 840,
  });

  const outcomeA = await promiseA;
  assert.equal(outcomeA.status, "cancelled");

  // Solo la URL de B permanece activa; la de A fue revocada
  assert.equal(tracker.activeUrls.size, 1);
  assert.equal(
    outcomeB.status === "valid" && pipeline.getCurrentPreviewUrl() === outcomeB.previewUrl,
    true
  );
});

test("renderiza CardImageUploader accesible en estado vacío y con vista previa 5:7 verificada", () => {
  assert.equal(formatImageByteSize(5_000_000).includes("5.00 MB"), true);

  const emptyHtml = renderToStaticMarkup(
    React.createElement(CardImageUploader, {
      value: null,
      onChange: () => {},
    })
  );

  assert.match(emptyHtml, /Imagen original de la carta/);
  assert.match(emptyHtml, /accept="image\/png,image\/jpeg,image\/webp"/);
  assert.match(emptyHtml, /Elegir archivo de imagen/);
  assert.match(emptyHtml, /600 × 840 px/);

  const validFile = createFakeFile(350_000, "image/png", "guardiana-solar.png");
  const previewHtml = renderToStaticMarkup(
    React.createElement(CardImageUploader, {
      value: {
        file: validFile,
        previewUrl: "blob:pokearena-test/preview-1",
        dimensions: { width: 600, height: 840 },
        sizeBytes: 350_000,
        mimeType: "image/png",
      },
      onChange: () => {},
    })
  );

  assert.match(previewHtml, /guardiana-solar\.png/);
  assert.match(previewHtml, /600 × 840 px/);
  assert.match(previewHtml, /aspect-\[5\/7\]/);
  assert.match(previewHtml, /Reemplazar imagen/);
  assert.match(previewHtml, /Eliminar imagen/);
});
