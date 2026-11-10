/** Hook para manejar el formulario de edición de deck. */

import { useCallback, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { updateDeck } from "../services/decks.api";
import { DECK_SIZE, type DeckSummary } from "../types/deck.types";

type EditDeckStatus = "idle" | "submitting" | "success" | "error";

interface UseEditDeckResult {
  name: string;
  selectedCardIds: string[];
  status: EditDeckStatus;
  errorMessage: string | null;
  setName: (name: string) => void;
  toggleCard: (cardId: string) => void;
  isCardSelected: (cardId: string) => boolean;
  canSubmit: boolean;
  submit: () => Promise<void>;
}

export function useEditDeck(
  deckId: string,
  initialName: string,
  initialCardIds: string[],
  onSuccess?: (deck: DeckSummary) => void,
): UseEditDeckResult {
  const [name, setName] = useState(initialName);
  const [selectedCardIds, setSelectedCardIds] = useState<string[]>(initialCardIds);
  const [status, setStatus] = useState<EditDeckStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const toggleCard = useCallback((cardId: string) => {
    setSelectedCardIds((prev) => {
      if (prev.includes(cardId)) return prev.filter((id) => id !== cardId);
      if (prev.length >= DECK_SIZE) return prev;
      return [...prev, cardId];
    });
  }, []);

  const isCardSelected = useCallback(
    (cardId: string) => selectedCardIds.includes(cardId),
    [selectedCardIds],
  );

  const canSubmit =
    name.trim().length > 0 &&
    selectedCardIds.length === DECK_SIZE &&
    status !== "submitting";

  const submit = useCallback(async () => {
    if (!canSubmit) return;
    setStatus("submitting");
    setErrorMessage(null);
    try {
      const deck = await updateDeck(deckId, { name: name.trim(), card_ids: selectedCardIds });
      setStatus("success");
      onSuccess?.(deck);
    } catch (err) {
      let msg = "No se pudo guardar el deck. Intenta de nuevo.";
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
  }, [deckId, canSubmit, name, selectedCardIds, onSuccess]);

  return { name, selectedCardIds, status, errorMessage, setName, toggleCard, isCardSelected, canSubmit, submit };
}
