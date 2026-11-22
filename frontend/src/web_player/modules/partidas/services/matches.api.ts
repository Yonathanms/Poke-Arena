/** Cliente HTTP para consulta de partidas activas e imágenes protegidas de estadios. */

import {
  requestApiWithMeta,
  type ApiResponse,
} from "../../../../shared/services/http-client";
import { ensureAuthHttpBridgeConfigured } from "../../../../web_admin/modules/auth/services/auth.api";
import type { ActiveMatchSummaryDTO, ActiveMatchViewDTO } from "../types/partidas.types";

const MATCHES_ENDPOINT = "/player/matches";
const LOCATIONS_ENDPOINT = "/content/locations";

export async function getActiveMatch(
  signal?: AbortSignal,
): Promise<ActiveMatchSummaryDTO | null> {
  ensureAuthHttpBridgeConfigured();
  const response = await requestApiWithMeta<ActiveMatchSummaryDTO | undefined>(
    `${MATCHES_ENDPOINT}/active`,
    {
      method: "GET",
      requiresAuth: true,
      signal,
    },
  );
  if (response.status === 204 || !response.data) {
    return null;
  }
  return response.data;
}

export async function getMatchView(
  matchId: string,
  ifNoneMatch?: string,
  signal?: AbortSignal,
): Promise<ApiResponse<ActiveMatchViewDTO>> {
  ensureAuthHttpBridgeConfigured();
  return requestApiWithMeta<ActiveMatchViewDTO>(
    `${MATCHES_ENDPOINT}/${encodeURIComponent(matchId)}`,
    {
      method: "GET",
      requiresAuth: true,
      ifNoneMatch,
      signal,
    },
  );
}

export async function fetchLocationImage(
  locationId: string,
  signal: AbortSignal,
): Promise<Blob> {
  ensureAuthHttpBridgeConfigured();
  const { data } = await requestApiWithMeta<Blob>(
    `${LOCATIONS_ENDPOINT}/${encodeURIComponent(locationId)}/image`,
    {
      method: "GET",
      requiresAuth: true,
      signal,
      headers: { Accept: "image/webp, image/png, */*" },
    },
    (response) => response.blob(),
  );
  if (data.size === 0) {
    throw new Error("La imagen del estadio recibida está vacía.");
  }
  return data;
}

export async function fetchLocationThumbnail(
  locationId: string,
  signal: AbortSignal,
): Promise<Blob> {
  ensureAuthHttpBridgeConfigured();
  const { data } = await requestApiWithMeta<Blob>(
    `${LOCATIONS_ENDPOINT}/${encodeURIComponent(locationId)}/thumbnail`,
    {
      method: "GET",
      requiresAuth: true,
      signal,
      headers: { Accept: "image/webp, image/png, */*" },
    },
    (response) => response.blob(),
  );
  if (data.size === 0) {
    throw new Error("La miniatura del estadio recibida está vacía.");
  }
  return data;
}
