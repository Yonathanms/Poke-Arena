/** Hook para manejar el formulario de creación de deck. */

import { useCallback, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { createDeck } from "../services/decks.api";
import { DECK_SIZE, type DeckSummary } from "../types/deck.types";

type CreateDeckStatus = "idle" | "submitting" | "success" | "error";

interface UseCreateDeckResult {
  name: string;
  selectedCardIds: string[];
  status: CreateDeckStatus;
  errorMessage: string | null;
  createdDeck: DeckSummary | null;
  setName: (name: string) => void;
  toggleCard: (cardId: string) => void;
  isCardSelected: (cardId: string) => boolean;
  canSubmit: boolean;
  submit: () => Promise<void>;
  reset: () => void;
}

export function useCreateDeck(onSuccess?: (deck: DeckSummary) => void): UseCreateDeckResult {
  const [name, setName] = useState("");
  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([]);
  const [status, setStatus] = useState<CreateDeckStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [createdDeck, setCreatedDeck] = useState<DeckSummary | null>(null);

  const toggleCard = useCallback((cardId: string) => {
    setSelectedCardIds((prev) => {
      if (prev.includes(cardId)) return prev.filter((id) => id !== cardId);
      if (prev.length >= DECK_SIZE) return prev;
      return [...prev, cardId];
    });
  }, []);

  const isCardSelected = useCallback(
    (cardId: string) => selectedCardIds.includes(cardId),
    [selectedCardIds]
  );

  const canSubmit =
    name.trim().length > 0 &&
    selectedCardIds.length === DECK_SIZE &&
    status !== "submitting";

  const submit = useCallback(async () => {
    if (!canSubmit) return;
    setStatus("submitting");
    setErrorMessage(null);

    const idempotencyKey = crypto.randomUUID();
    try {
      const deck = await createDeck(
        { name: name.trim(), card_ids: selectedCardIds },
        idempotencyKey
      );
      setCreatedDeck(deck);
      setStatus("success");
      onSuccess?.(deck);
    } catch (err) {
      let msg = "No se pudo crear el deck. Intenta de nuevo.";
      if (err instanceof ApiHttpError) {
        if (err.code === "deck_nombre_ocupado") {
          msg = `Ya tienes un deck llamado "${name.trim()}". Elige otro nombre.`;
        } else if (err.detail) {
          msg = err.detail;
        }
      }
      setErrorMessage(msg);
      setStatus("error");
    }
  }, [canSubmit, name, selectedCardIds, onSuccess]);

  const reset = useCallback(() => {
    setName("");
    setSelectedCardIds([]);
    setStatus("idle");
    setErrorMessage(null);
    setCreatedDeck(null);
  }, []);

  return {
    name,
    selectedCardIds,
    status,
    errorMessage,
    createdDeck,
    setName,
    toggleCard,
    isCardSelected,
    canSubmit,
    submit,
    reset,
  };
}
