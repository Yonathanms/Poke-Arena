/** Tipos de dominio para decks y colección del jugador. */

export interface DeckSummary {
  readonly id: string;
  readonly name: string;
  readonly card_count: number;
  readonly created_at: string;
}

export interface DeckDetail {
  readonly id: string;
  readonly name: string;
  readonly card_ids: string[];
  readonly created_at: string;
}

export interface PlayerCard {
  readonly id: string;
  readonly code: string;
  readonly name: string;
  readonly card_type: string;
  readonly rarity: string;
  readonly quantity: number;
}

export interface CreateDeckPayload {
  readonly name: string;
  readonly card_ids: string[];
}

export interface EditDeckPayload {
  readonly name: string;
  readonly card_ids: string[];
}

export const DECK_SIZE = 12;
