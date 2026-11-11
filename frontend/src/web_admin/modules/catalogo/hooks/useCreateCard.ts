/**
 * Hook para gestionar el formulario de Crear Carta (US 2.1.1).
 * Coordina los valores del formulario, la previsualización de la imagen,
 * las validaciones de negocio y el envío idempotente al backend.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { submitCreateCardMultipart } from "../services/catalog.api";
import type {
  CardCreatedResponseDTO,
  CardFieldErrors,
  CreateCardFormValues,
  ValidatedCardImageSelection,
} from "../types/card-admin.types";
import { validateCreateCardForm } from "../validation/card-validation";

const INITIAL_VALUES: CreateCardFormValues = {
  name: "",
  cost: 0,
  power: 0,
  card_type: "FUE",
  rarity: "COMUN",
  ability_code: "HAB-000",
};

function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function formatServerError(error: unknown): {
  readonly message: string;
  readonly fieldError?: Partial<CardFieldErrors>;
} {
  if (error instanceof ApiHttpError) {
    if (error.status === 401) {
      return {
        message: "No estás autenticado o tu sesión expiró. Inicia sesión para continuar.",
      };
    }
    if (error.status === 403) {
      return {
        message: "No tienes permisos de administrador para crear cartas en el catálogo.",
      };
    }
    if (error.status === 413 || error.status === 415 || error.code === "imagen_invalida") {
      return {
        message: error.detail || "La imagen no cumple con los requisitos del catálogo.",
        fieldError: { image: error.detail },
      };
    }
    if (error.code === "habilidad_inexistente") {
      return {
        message: error.detail || "El código de habilidad seleccionado no existe.",
        fieldError: { ability_code: error.detail },
      };
    }
    return {
      message: error.detail || `No se pudo crear la carta (Error HTTP ${error.status}).`,
    };
  }

  return {
    message:
      error instanceof Error ? error.message : "Ocurrió un error inesperado al guardar la carta.",
  };
}

export interface UseCreateCardResult {
  readonly values: CreateCardFormValues;
  readonly imageSelection: ValidatedCardImageSelection | null;
  readonly errors: CardFieldErrors;
  readonly isSubmitting: boolean;
  readonly serverError: string | null;
  readonly successCard: CardCreatedResponseDTO | null;
  readonly handleChange: <K extends keyof CreateCardFormValues>(
    field: K,
    value: CreateCardFormValues[K]
  ) => void;
  readonly handleImageChange: (
    selection: ValidatedCardImageSelection | null,
    validationError?: string | null
  ) => void;
  readonly submit: (availableAbilityCodes?: ReadonlyArray<string>) => Promise<void>;
  readonly reset: () => void;
  readonly dismissServerError: () => void;
}

export function useCreateCard(): UseCreateCardResult {
  const [values, setValues] = useState<CreateCardFormValues>(INITIAL_VALUES);
  const [imageSelection, setImageSelection] = useState<ValidatedCardImageSelection | null>(null);
  const [errors, setErrors] = useState<CardFieldErrors>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [successCard, setSuccessCard] = useState<CardCreatedResponseDTO | null>(null);

  const idempotencyKeyRef = useRef<string>(generateUUID());
  const activePreviewUrlRef = useRef<string | null>(null);

  const revokeCurrentPreview = useCallback(() => {
    if (activePreviewUrlRef.current) {
      URL.revokeObjectURL(activePreviewUrlRef.current);
      activePreviewUrlRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      revokeCurrentPreview();
    };
  }, [revokeCurrentPreview]);

  const handleChange = useCallback(
    <K extends keyof CreateCardFormValues>(field: K, value: CreateCardFormValues[K]) => {
      setValues((prev) => ({ ...prev, [field]: value }));
      setErrors((prev) => {
        if (!prev[field]) return prev;
        const next = { ...prev };
        delete next[field];
        return next;
      });
      setServerError(null);
      // Al modificar los datos se genera una clave nueva para evitar conflictos de payload
      idempotencyKeyRef.current = generateUUID();
    },
    []
  );

  const handleImageChange = useCallback(
    (selection: ValidatedCardImageSelection | null, validationError?: string | null) => {
      if (activePreviewUrlRef.current && activePreviewUrlRef.current !== selection?.previewUrl) {
        URL.revokeObjectURL(activePreviewUrlRef.current);
      }
      activePreviewUrlRef.current = selection?.previewUrl ?? null;
      setImageSelection(selection);

      setErrors((prev) => {
        const next = { ...prev };
        if (validationError) {
          next.image = validationError;
        } else {
          delete next.image;
        }
        return next;
      });
      setServerError(null);
      idempotencyKeyRef.current = generateUUID();
    },
    []
  );

  const submit = useCallback(
    async (availableAbilityCodes?: ReadonlyArray<string>) => {
      if (isSubmitting) return;

      setServerError(null);

      const validation = validateCreateCardForm(values, {
        availableAbilityCodes,
        imageCandidate: imageSelection
          ? {
              sizeBytes: imageSelection.sizeBytes,
              mimeType: imageSelection.mimeType,
              fileName: imageSelection.file.name,
            }
          : null,
        imageDimensions: imageSelection ? imageSelection.dimensions : null,
      });

      if (!validation.valid || !validation.normalizedValues || !imageSelection) {
        setErrors(validation.errors);
        return;
      }

      setErrors({});
      setIsSubmitting(true);

      try {
        const response = await submitCreateCardMultipart(
          {
            ...validation.normalizedValues,
            image: imageSelection.file,
            imageFileName: imageSelection.file.name,
          },
          idempotencyKeyRef.current
        );

        setSuccessCard(response.data);
        idempotencyKeyRef.current = generateUUID();
      } catch (err: unknown) {
        const formatted = formatServerError(err);
        setServerError(formatted.message);
        if (formatted.fieldError) {
          setErrors((prev) => ({ ...prev, ...formatted.fieldError }));
        }
        // Si fue un rechazo de validación (4xx excepto 409 en curso), rotamos la clave para el próximo envío
        if (err instanceof ApiHttpError && err.status >= 400 && err.status < 500 && err.status !== 409) {
          idempotencyKeyRef.current = generateUUID();
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, values, imageSelection]
  );

  const reset = useCallback(() => {
    revokeCurrentPreview();
    setValues(INITIAL_VALUES);
    setImageSelection(null);
    setErrors({});
    setServerError(null);
    setSuccessCard(null);
    idempotencyKeyRef.current = generateUUID();
  }, [revokeCurrentPreview]);

  const dismissServerError = useCallback(() => {
    setServerError(null);
  }, []);

  return {
    values,
    imageSelection,
    errors,
    isSubmitting,
    serverError,
    successCard,
    handleChange,
    handleImageChange,
    submit,
    reset,
    dismissServerError,
  };
}
