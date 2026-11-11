// Hook de estado y mutación para crear una ubicación
import { useCallback, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { createLocation } from "../services/catalog.api";
import type {
  CreateLocationFormValues,
  LocationResponseDTO,
} from "../types/location-admin.types";

interface State {
  loading: boolean;
  error: string | null;
  success: LocationResponseDTO | null;
}

function formatLocationError(err: unknown): string {
  if (err instanceof ApiHttpError) {
    if (err.status === 401) {
      return "No estás autenticado o tu sesión expiró. Inicia sesión para continuar.";
    }
    if (err.status === 403) {
      return "No tienes permisos de administrador para crear ubicaciones en el catálogo.";
    }
    return err.detail || `No se pudo crear la ubicación (Error HTTP ${err.status}).`;
  }

  if (err instanceof Error && err.message) {
    return err.message;
  }

  return "Error inesperado al crear la ubicación.";
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

    // Siguiente paso: construir FormData y llamar al API usando la sesión autenticada
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
      const result = await createLocation(formData, idempotencyKeyRef.current);
      idempotencyKeyRef.current = crypto.randomUUID();
      setState({ loading: false, error: null, success: result });
    } catch (err: unknown) {
      if (err instanceof ApiHttpError && err.status >= 400 && err.status < 500 && err.status !== 409) {
        idempotencyKeyRef.current = crypto.randomUUID();
      }
      setState({ loading: false, error: formatLocationError(err), success: null });
    }
  }, []);

  const reset = useCallback(() => {
    idempotencyKeyRef.current = crypto.randomUUID();
    setState({ loading: false, error: null, success: null });
  }, []);

  return { ...state, submitLocation, reset };
}
