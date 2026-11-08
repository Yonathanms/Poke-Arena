// Hook de estado y mutación para crear una ubicación
import { useCallback, useRef, useState } from "react";
import { createLocation } from "../services/catalog.api";
import type {
  CreateLocationFormValues,
  LocationResponseDTO,
} from "../types/location-admin.types";

// Placeholder: reemplazar con token real cuando el módulo de identidad esté listo
const TOKEN_PLACEHOLDER = "admin-token-placeholder";

interface State {
  loading: boolean;
  error: string | null;
  success: LocationResponseDTO | null;
}

export function useCreateLocation() {
  const [state, setState] = useState<State>({ loading: false, error: null, success: null });
  const idempotencyKeyRef = useRef(crypto.randomUUID());

  const submitLocation = useCallback(async (values: CreateLocationFormValues) => {
    
    // Verifica imagen no nula
    if (!values.imagen) {
      setState((s) => ({ ...s, error: "Debe seleccionar una imagen." }));
      return;
    }

    setState({ loading: true, error: null, success: null });

    // Siguiente paso: construir FormData y llamar al API
    const formData = new FormData();
    formData.append("nombre", values.nombre);
    formData.append("descripcion", values.descripcion);
    formData.append("card_limit", String(values.card_limit));
    formData.append("energia_tipo", values.energia_tipo);
    formData.append("energia_valor", String(values.energia_valor));
    formData.append("efecto_tipo", values.efecto_tipo);
    formData.append("efecto_params", JSON.stringify(values.efecto_params));
    formData.append("imagen", values.imagen);

    try {
      // Intenta crear ubicación
      const result = await createLocation(formData, idempotencyKeyRef.current, TOKEN_PLACEHOLDER);
      idempotencyKeyRef.current = crypto.randomUUID();
      setState({ loading: false, error: null, success: result });
    } catch (err: unknown) {
      const e = err as { detail?: string | object };
      const msg =
        typeof e.detail === "string"
          ? e.detail
          : typeof e.detail === "object"
            ? JSON.stringify(e.detail)
            : "Error inesperado al crear la ubicación.";
      setState({ loading: false, error: msg, success: null });
    }
  }, []);

  const reset = useCallback(() => {
    setState({ loading: false, error: null, success: null });
  }, []);

  return { ...state, submitLocation, reset };
}
