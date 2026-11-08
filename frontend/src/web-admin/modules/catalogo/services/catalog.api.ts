// Llamadas HTTP al catálogo del backend (/api/v1/content/*)
import type { LocationResponseDTO } from "../types/location-admin.types";

const API_BASE = "http://localhost:8000/api/v1";

export async function createLocation(
  formData: FormData,
  idempotencyKey: string,
  token: string,
): Promise<LocationResponseDTO> {
  // Siguiente paso: enviar solicitud al endpoint de ubicaciones
  const response = await fetch(`${API_BASE}/content/locations`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "idempotency-key": idempotencyKey,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw { status: response.status, detail: error.detail ?? "Error al crear ubicación." };
  }

  return response.json();
}
