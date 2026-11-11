/**
 * Selector y validador de imagen para Crear Carta (US 2.1.1).
 * Verifica formato (PNG, JPG, WebP), peso máximo (5 MB), proporción 5:7 y resolución >= 600×840 px.
 */

import React, { useId, useRef, useState } from "react";
import {
  CheckCircle2,
  FileImage,
  ImagePlus,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import type { ValidatedCardImageSelection } from "../types/card-admin.types";
import {
  ALLOWED_IMAGE_MIME_TYPES,
  CARD_VALIDATION_CONSTRAINTS,
  validateAndInspectCardImage,
} from "../validation/card-validation";

export interface CardImageUploaderProps {
  readonly value: ValidatedCardImageSelection | null;
  readonly onChange: (
    selection: ValidatedCardImageSelection | null,
    validationError?: string | null
  ) => void;
  readonly disabled?: boolean;
  readonly error?: string | null;
}

export function formatImageByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes < 1000) return `${bytes} B`;
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} KB`;
  return `${(bytes / 1_000_000).toFixed(2)} MB`;
}

export function CardImageUploader({
  value,
  onChange,
  disabled = false,
  error = null,
}: CardImageUploaderProps): React.ReactElement {
  const uploaderId = useId();
  const fileInputId = `${uploaderId}-file-input`;
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [isInspecting, setIsInspecting] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFile = async (file: File | null | undefined): Promise<void> => {
    if (!file || disabled) return;

    setIsInspecting(true);
    const result = await validateAndInspectCardImage(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setIsInspecting(false);

    if (!result.valid) {
      onChange(null, result.error);
      return;
    }

    onChange(result.selection, null);
  };

  const handleRemove = (): void => {
    if (disabled) return;
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onChange(null, null);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label
          htmlFor={fileInputId}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
        >
          Imagen de la carta <span className="text-red-400">*</span>
        </label>
        <span className="font-mono text-[11px] text-slate-400">
          5:7 · Mín. {CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_WIDTH}×
          {CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_HEIGHT} px · Máx. 5 MB
        </span>
      </div>

      <input
        ref={fileInputRef}
        id={fileInputId}
        type="file"
        accept={ALLOWED_IMAGE_MIME_TYPES.join(",")}
        disabled={disabled || isInspecting}
        onChange={(e) => void handleFile(e.currentTarget.files?.[0])}
        className="sr-only"
      />

      {error && (
        <AlertBanner
          variant="error"
          title="Imagen no válida"
          description={error}
          onDismiss={() => onChange(value, null)}
        />
      )}

      {!value ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled && !isInspecting) setIsDragOver(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setIsDragOver(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragOver(false);
            if (!disabled && !isInspecting) {
              void handleFile(e.dataTransfer.files?.[0]);
            }
          }}
          className={`rounded-2xl border-2 border-dashed p-6 transition ${
            isDragOver
              ? "border-arena-accent bg-blue-500/10"
              : error
                ? "border-red-500/40 bg-arena-surface/40"
                : "border-arena-border bg-arena-surface/50 hover:border-slate-600"
          }`}
        >
          <div className="flex flex-col items-center justify-center text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-arena-border bg-arena-card text-blue-400">
              {isInspecting ? (
                <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
              ) : (
                <ImagePlus className="h-6 w-6" aria-hidden="true" />
              )}
            </div>

            <p className="text-sm font-semibold text-slate-100">
              {isInspecting
                ? "Verificando imagen..."
                : "Selecciona o arrastra la ilustración de la carta"}
            </p>

            <p className="mt-1.5 max-w-md text-xs text-slate-400">
              Formatos: <strong className="text-slate-300">PNG, JPG o WebP</strong> (máx. 5 MB).
              Resolución mínima de <strong className="text-slate-300">600 × 840 px</strong> en
              proporción vertical <strong className="text-slate-300">5:7</strong>.
            </p>

            <button
              type="button"
              disabled={disabled || isInspecting}
              onClick={() => fileInputRef.current?.click()}
              className="mt-4 inline-flex items-center gap-2 rounded-xl bg-arena-accent px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:opacity-60"
            >
              <FileImage className="h-4 w-4" aria-hidden="true" />
              <span>Elegir imagen</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-arena-border bg-arena-surface/70 p-4">
          <div className="grid gap-4 sm:grid-cols-[120px_1fr] items-center">
            <div className="mx-auto w-28 aspect-[5/7] overflow-hidden rounded-xl border border-arena-border bg-arena-card">
              <img
                src={value.previewUrl}
                alt={value.file.name}
                className="h-full w-full object-cover"
              />
            </div>

            <div className="space-y-3">
              <div>
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                  5:7 válida ({value.dimensions.width}×{value.dimensions.height} px ·{" "}
                  {formatImageByteSize(value.sizeBytes)})
                </span>
                <p className="mt-1.5 truncate text-sm font-bold text-slate-100" title={value.file.name}>
                  {value.file.name}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={disabled || isInspecting}
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-arena-border bg-arena-card px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-blue-500/50 hover:text-white disabled:opacity-60"
                >
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Cambiar</span>
                </button>

                <button
                  type="button"
                  disabled={disabled || isInspecting}
                  onClick={handleRemove}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-200 hover:bg-red-500/20 disabled:opacity-60"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Quitar</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
