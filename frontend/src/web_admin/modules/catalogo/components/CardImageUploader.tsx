/**
 * Componente visual de selección, validación y previsualización de imagen para
 * 2.1.1 — Crear Carta (`CardImageUploader.tsx`).
 *
 * Responsabilidades:
 * 1. Permitir elegir un archivo PNG, JPEG o WebP mediante input accesible o drag-and-drop.
 * 2. Validar tamaño (`1..5_000_000` bytes exactos), formato MIME, resolución mínima
 *    (`600 × 840` px), proporción exacta `5:7` (`7 * width === 5 * height`) y límite
 *    de `20_000_000` píxeles reutilizando `card-validation.ts`.
 * 3. Decodificar dimensiones reales en el navegador (`createImageBitmap` con fallback
 *    a `HTMLImageElement`), gestionando el ciclo de vida de `URL.createObjectURL` y
 *    `URL.revokeObjectURL` mediante `SequentialImageSelectionPipeline` para impedir fugas
 *    de memoria y condiciones de carrera al seleccionar múltiples archivos rápidamente.
 * 4. Mostrar la previsualización en relación de aspecto `5:7`, metadatos del archivo y
 *    controles para reemplazar o eliminar la selección, comunicando el resultado al
 *    componente padre sin realizar peticiones HTTP ni comprimir/modificar el archivo original.
 */

import React, { useEffect, useId, useRef, useState } from "react";
import {
  CheckCircle2,
  FileImage,
  ImagePlus,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import type {
  ImageDimensions,
  ValidatedCardImageSelection,
} from "../types/card-admin.types";
import {
  ALLOWED_IMAGE_MIME_TYPES,
  CARD_VALIDATION_CONSTRAINTS,
  SequentialImageSelectionPipeline,
  type ImageDimensionsDecoder,
  type ObjectUrlManager,
} from "../validation/card-validation";

export interface CardImageUploaderProps {
  readonly value: ValidatedCardImageSelection | null;
  readonly onChange: (selection: ValidatedCardImageSelection | null) => void;
  readonly onValidationErrorChange?: (errorMessage: string | null) => void;
  readonly disabled?: boolean;
  readonly externalError?: string | null;
  /** Inyección opcional para pruebas deterministas de decodificación y Object URLs. */
  readonly customUrlManager?: ObjectUrlManager;
  readonly customDimensionsDecoder?: ImageDimensionsDecoder;
}

/**
 * Formatea una cantidad de bytes en una representación legible para el administrador,
 * mostrando también el conteo exacto cuando está cerca del límite de 5 000 000 bytes.
 */
export function formatImageByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "0 B";
  }
  if (bytes < 1000) {
    return `${bytes} B`;
  }
  if (bytes < 1_000_000) {
    return `${(bytes / 1000).toFixed(1)} KB (${bytes.toLocaleString("es-CR")} bytes)`;
  }
  return `${(bytes / 1_000_000).toFixed(2)} MB (${bytes.toLocaleString("es-CR")} bytes)`;
}

/**
 * Decodificador de dimensiones reales en el navegador.
 * Prioriza `createImageBitmap(file)` (que aplica `imageOrientation: "from-image"` por
 * defecto en navegadores modernos, coincidiendo con `ImageOps.exif_transpose` de Pillow)
 * y cierra el bitmap inmediatamente con `bitmap.close()` para liberar memoria GPU/RAM.
 * Si `createImageBitmap` no está disponible, utiliza `HTMLImageElement` sobre el `objectUrl`.
 */
export async function decodeBrowserImageDimensions(
  file: Blob,
  objectUrl: string
): Promise<ImageDimensions> {
  if (typeof globalThis.createImageBitmap === "function") {
    const bitmap = await globalThis.createImageBitmap(file);
    try {
      return {
        width: bitmap.width,
        height: bitmap.height,
      };
    } finally {
      if (typeof bitmap.close === "function") {
        bitmap.close();
      }
    }
  }

  return new Promise<ImageDimensions>((resolve, reject) => {
    if (typeof Image === "undefined") {
      reject(new Error("Entorno sin decodificador de imágenes DOM."));
      return;
    }
    const img = new Image();
    img.onload = () => {
      resolve({
        width: img.naturalWidth,
        height: img.naturalHeight,
      });
    };
    img.onerror = () => {
      reject(new Error("Fallo al cargar la imagen en HTMLImageElement."));
    };
    img.src = objectUrl;
  });
}

const DEFAULT_URL_MANAGER: ObjectUrlManager = {
  createObjectURL: (blob: Blob) => URL.createObjectURL(blob),
  revokeObjectURL: (url: string) => URL.revokeObjectURL(url),
};

export function CardImageUploader({
  value,
  onChange,
  onValidationErrorChange,
  disabled = false,
  externalError = null,
  customUrlManager,
  customDimensionsDecoder,
}: CardImageUploaderProps): React.ReactElement {
  const uploaderId = useId();
  const fileInputId = `${uploaderId}-file-input`;
  const requirementsId = `${uploaderId}-requirements`;
  const errorId = `${uploaderId}-error`;

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pipelineRef = useRef<SequentialImageSelectionPipeline | null>(null);

  if (pipelineRef.current === null) {
    pipelineRef.current = new SequentialImageSelectionPipeline({
      urlManager: customUrlManager ?? DEFAULT_URL_MANAGER,
      decodeDimensions: customDimensionsDecoder ?? decodeBrowserImageDimensions,
    });
  }

  const [isInspecting, setIsInspecting] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Al desmontar el componente, revoca cualquier URL temporal activa e invalida decodificaciones pendientes
  useEffect(() => {
    const pipeline = pipelineRef.current;
    return () => {
      pipeline?.clearActiveSelection();
    };
  }, []);

  const updateValidationError = (message: string | null): void => {
    setValidationError(message);
    onValidationErrorChange?.(message);
  };

  const resetNativeInput = (): void => {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleFileCandidate = async (file: File | null | undefined): Promise<void> => {
    if (!file || disabled || !pipelineRef.current) {
      return;
    }

    setIsInspecting(true);
    updateValidationError(null);

    const outcome = await pipelineRef.current.inspectFile(file);
    resetNativeInput();

    if (outcome.status === "cancelled") {
      return;
    }

    setIsInspecting(false);

    if (outcome.status === "invalid") {
      onChange(null);
      updateValidationError(outcome.errorMessage);
      return;
    }

    updateValidationError(null);
    onChange({
      file,
      previewUrl: outcome.previewUrl,
      dimensions: outcome.dimensions,
      sizeBytes: outcome.sizeBytes,
      mimeType: outcome.mimeType,
    });
  };

  const handleRemoveSelection = (): void => {
    if (disabled) {
      return;
    }
    pipelineRef.current?.clearActiveSelection();
    resetNativeInput();
    setIsInspecting(false);
    updateValidationError(null);
    onChange(null);
  };

  const handleTriggerFileDialog = (): void => {
    if (disabled || isInspecting) {
      return;
    }
    fileInputRef.current?.click();
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    event.stopPropagation();
    if (!disabled && !isInspecting) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
    if (disabled || isInspecting) {
      return;
    }
    const droppedFile = event.dataTransfer.files?.[0];
    if (droppedFile) {
      void handleFileCandidate(droppedFile);
    }
  };

  const activeError = validationError ?? externalError;
  const acceptAttribute = ALLOWED_IMAGE_MIME_TYPES.join(",");

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label
          htmlFor={fileInputId}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
        >
          Imagen original de la carta <span className="text-red-400">*</span>
        </label>
        <span className="text-[11px] font-mono text-slate-400">
          Proporción 5:7 · Mín. {CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_WIDTH}×
          {CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_HEIGHT} px · Máx. 5 000 000 B
        </span>
      </div>

      {/* Input file nativo accesible */}
      <input
        ref={fileInputRef}
        id={fileInputId}
        type="file"
        accept={acceptAttribute}
        disabled={disabled || isInspecting}
        aria-invalid={activeError !== null}
        aria-describedby={activeError ? `${requirementsId} ${errorId}` : requirementsId}
        onChange={(event) => {
          const selected = event.currentTarget.files?.[0];
          void handleFileCandidate(selected);
        }}
        className="sr-only"
      />

      {activeError && (
        <div id={errorId}>
          <AlertBanner
            variant="error"
            title="Imagen no válida"
            description={activeError}
            onDismiss={() => updateValidationError(null)}
          />
        </div>
      )}

      {!value ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`rounded-2xl border-2 border-dashed p-6 transition ${
            isDragOver
              ? "border-arena-accent bg-blue-500/10"
              : activeError
                ? "border-red-500/40 bg-arena-surface/40"
                : "border-arena-border bg-arena-surface/50 hover:border-slate-600"
          }`}
        >
          <div className="flex flex-col items-center justify-center text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-arena-border bg-arena-card text-blue-400 shadow-inner">
              {isInspecting ? (
                <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
              ) : (
                <ImagePlus className="h-6 w-6" aria-hidden="true" />
              )}
            </div>

            <p className="text-sm font-semibold text-slate-100">
              {isInspecting
                ? "Verificando dimensiones y formato de la imagen..."
                : "Selecciona o arrastra la ilustración de la carta"}
            </p>

            <p id={requirementsId} className="mt-1.5 max-w-md text-xs leading-relaxed text-slate-400">
              Formatos aceptados: <strong className="text-slate-300">PNG, JPEG o WebP</strong> (un solo cuadro). Tamaño entre 1 y{" "}
              <strong className="text-slate-300">5 000 000 bytes</strong>. Resolución mínima{" "}
              <strong className="text-slate-300">600 × 840 px</strong> con relación exacta{" "}
              <strong className="text-slate-300">5:7</strong> (máximo 20 MP). El servidor verificará los bytes y generará la miniatura WebP de 200 × 280 px.
            </p>

            <div className="mt-4">
              <button
                type="button"
                disabled={disabled || isInspecting}
                onClick={handleTriggerFileDialog}
                className="inline-flex items-center gap-2 rounded-xl bg-arena-accent px-4 py-2 text-xs font-semibold text-white shadow-md shadow-blue-600/20 transition hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <FileImage className="h-4 w-4" aria-hidden="true" />
                <span>Elegir archivo de imagen</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-arena-border bg-arena-surface/70 p-4 sm:p-5">
          <div className="grid gap-5 sm:grid-cols-[160px_1fr] items-start">
            {/* Contenedor de vista previa en proporción exacta 5:7 */}
            <div className="mx-auto w-40 aspect-[5/7] overflow-hidden rounded-xl border border-arena-border bg-arena-card shadow-lg">
              <img
                src={value.previewUrl}
                alt={`Vista previa de la imagen seleccionada (${value.file.name})`}
                className="h-full w-full object-cover"
              />
            </div>

            {/* Metadatos verificados y acciones */}
            <div className="flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Proporción 5:7 verificada en cliente
                  </span>
                  <span className="rounded-md border border-arena-border bg-arena-card px-2 py-0.5 font-mono text-[11px] text-slate-300">
                    {value.mimeType.replace("image/", "").toUpperCase()}
                  </span>
                </div>

                <p
                  className="truncate text-sm font-bold text-slate-100"
                  title={value.file.name}
                >
                  {value.file.name}
                </p>

                <dl className="grid grid-cols-2 gap-2 rounded-xl border border-arena-border/70 bg-arena-card/70 p-3 text-xs">
                  <div>
                    <dt className="text-[11px] uppercase tracking-wider text-slate-400">
                      Resolución
                    </dt>
                    <dd className="mt-0.5 font-mono font-semibold text-slate-200">
                      {value.dimensions.width} × {value.dimensions.height} px
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-wider text-slate-400">
                      Tamaño original
                    </dt>
                    <dd className="mt-0.5 font-mono font-semibold text-slate-200">
                      {formatImageByteSize(value.sizeBytes)}
                    </dd>
                  </div>
                </dl>

                <p id={requirementsId} className="text-[11px] text-slate-400">
                  El archivo original se conserva intacto; FastAPI validará el binario y generará la miniatura oficial de 200 × 280 px al guardar la carta.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5 pt-1">
                <button
                  type="button"
                  disabled={disabled || isInspecting}
                  onClick={handleTriggerFileDialog}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-arena-border bg-arena-card px-3.5 py-2 text-xs font-semibold text-slate-200 transition hover:border-blue-500/50 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Reemplazar imagen</span>
                </button>

                <button
                  type="button"
                  disabled={disabled || isInspecting}
                  onClick={handleRemoveSelection}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3.5 py-2 text-xs font-semibold text-red-200 transition hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Eliminar imagen</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
