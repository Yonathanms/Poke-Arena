/**
 * Servicio API para consultar el perfil del jugador autenticado (`GET /api/v1/identity/me`).
 */

import { requestApi } from "../../../../shared/services/http-client";
import type { PlayerProfileDTO } from "../types/vista_principal.types";

export async function fetchAuthenticatedProfile(): Promise<PlayerProfileDTO> {
  return requestApi<PlayerProfileDTO>("/identity/me", {
    method: "GET",
    requiresAuth: true,
  });
}

