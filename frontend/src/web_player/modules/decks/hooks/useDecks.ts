/** Hook para cargar y recargar la lista de decks del jugador. */

import { useCallback, useEffect, useState } from "react";
import type { DeckSummary } from "../types/deck.types";
import { listDecks } from "../services/decks.api";

interface UseDecksResult {
  decks: DeckSummary[];
  deckCount: number;
  isLoading: boolean;
  error: string | null;
  reload: () => void;
}

export function useDecks(): UseDecksResult {
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    listDecks()
      .then((data) => {
        if (!cancelled) setDecks(data);
      })
      .catch(() => {
        if (!cancelled) setError("No se pudieron cargar los decks.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => { cancelled = true; };
  }, [tick]);

  return { decks, deckCount: decks.length, isLoading, error, reload };
}
