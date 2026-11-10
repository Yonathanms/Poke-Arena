/** API para consultar la colección de cartas del jugador. */

import { requestApi } from "../../../../shared/services/http-client";
import { ensureAuthHttpBridgeConfigured } from "../../../../web_admin/modules/auth/services/auth.api";
import type { PlayerCard } from "../types/deck.types";

const CARDS_ENDPOINT = "/player/cards";

export async function getPlayerCards(): Promise<PlayerCard[]> {
  ensureAuthHttpBridgeConfigured();
  return requestApi<PlayerCard[]>(CARDS_ENDPOINT, { method: "GET", requiresAuth: true });
}
