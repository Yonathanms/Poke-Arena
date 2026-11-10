/** API para decks del jugador. */

import { requestApi, requestApiWithMeta } from "../../../../shared/services/http-client";
import { ensureAuthHttpBridgeConfigured } from "../../../../web_admin/modules/auth/services/auth.api";
import type { CreateDeckPayload, DeckDetail, DeckSummary, EditDeckPayload } from "../types/deck.types";

const DECKS_ENDPOINT = "/player/decks";

export async function listDecks(): Promise<DeckSummary[]> {
  ensureAuthHttpBridgeConfigured();
  return requestApi<DeckSummary[]>(DECKS_ENDPOINT, { method: "GET", requiresAuth: true });
}

export async function getDeck(deckId: string): Promise<DeckDetail> {
  ensureAuthHttpBridgeConfigured();
  return requestApi<DeckDetail>(`${DECKS_ENDPOINT}/${encodeURIComponent(deckId)}`, {
    method: "GET",
    requiresAuth: true,
  });
}

export async function createDeck(
  payload: CreateDeckPayload,
  idempotencyKey: string
): Promise<DeckSummary> {
  ensureAuthHttpBridgeConfigured();
  const response = await requestApiWithMeta<DeckSummary>(DECKS_ENDPOINT, {
    method: "POST",
    requiresAuth: true,
    body: payload as unknown as Record<string, unknown>,
    idempotencyKey,
  });
  return response.data;
}

export async function updateDeck(deckId: string, payload: EditDeckPayload): Promise<DeckSummary> {
  ensureAuthHttpBridgeConfigured();
  return requestApi<DeckSummary>(`${DECKS_ENDPOINT}/${encodeURIComponent(deckId)}`, {
    method: "PUT",
    requiresAuth: true,
    body: payload as unknown as Record<string, unknown>,
  });
}

export async function deleteDeck(deckId: string): Promise<void> {
  ensureAuthHttpBridgeConfigured();
  await requestApi<void>(`${DECKS_ENDPOINT}/${encodeURIComponent(deckId)}`, {
    method: "DELETE",
    requiresAuth: true,
  });
}
