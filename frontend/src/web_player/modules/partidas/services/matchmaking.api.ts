/** Cliente HTTP para cola de emparejamiento, heartbeat, cancelación y duelo contra Bot. */

import {
  requestApiWithMeta,
  type ApiResponse,
} from "../../../../shared/services/http-client";
import { ensureAuthHttpBridgeConfigured } from "../../../../web_admin/modules/auth/services/auth.api";
import type { MatchContext, MatchSearchDTO } from "../types/partidas.types";

const MATCHMAKING_ENDPOINT = "/player/matchmaking";

export async function startMatchmaking(
  deckId: string,
  context: MatchContext,
): Promise<ApiResponse<MatchSearchDTO>> {
  ensureAuthHttpBridgeConfigured();
  return requestApiWithMeta<MatchSearchDTO>(MATCHMAKING_ENDPOINT, {
    method: "POST",
    requiresAuth: true,
    body: { deck_id: deckId, context },
  });
}

export async function getCurrentMatchmaking(
  ifNoneMatch?: string,
  signal?: AbortSignal,
): Promise<ApiResponse<MatchSearchDTO | undefined>> {
  ensureAuthHttpBridgeConfigured();
  return requestApiWithMeta<MatchSearchDTO | undefined>(`${MATCHMAKING_ENDPOINT}/current`, {
    method: "GET",
    requiresAuth: true,
    ifNoneMatch,
    signal,
  });
}

export async function getMatchmakingById(
  searchId: string,
  ifNoneMatch?: string,
  signal?: AbortSignal,
): Promise<ApiResponse<MatchSearchDTO>> {
  ensureAuthHttpBridgeConfigured();
  return requestApiWithMeta<MatchSearchDTO>(
    `${MATCHMAKING_ENDPOINT}/${encodeURIComponent(searchId)}`,
    {
      method: "GET",
      requiresAuth: true,
      ifNoneMatch,
      signal,
    },
  );
}

export async function cancelMatchmaking(
  searchId: string,
): Promise<ApiResponse<MatchSearchDTO>> {
  ensureAuthHttpBridgeConfigured();
  return requestApiWithMeta<MatchSearchDTO>(
    `${MATCHMAKING_ENDPOINT}/${encodeURIComponent(searchId)}`,
    {
      method: "DELETE",
      requiresAuth: true,
    },
  );
}

export async function acceptBotMatch(
  searchId: string,
): Promise<ApiResponse<MatchSearchDTO>> {
  ensureAuthHttpBridgeConfigured();
  return requestApiWithMeta<MatchSearchDTO>(
    `${MATCHMAKING_ENDPOINT}/${encodeURIComponent(searchId)}/accept-bot`,
    {
      method: "POST",
      requiresAuth: true,
    },
  );
}
