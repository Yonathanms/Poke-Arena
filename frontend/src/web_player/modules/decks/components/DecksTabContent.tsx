/** Contenido del tab Decks: lista inline con acciones de crear, editar y eliminar. */

import React, { useState } from "react";
import { deleteDeck } from "../services/decks.api";
import { useDecks } from "../hooks/useDecks";

interface DecksTabContentProps {
  readonly onCreateDeck: () => void;
  readonly onEditDeck: (deckId: string) => void;
  readonly onDecksChanged: () => void;
}

export function DecksTabContent({
  onCreateDeck,
  onEditDeck,
  onDecksChanged,
}: DecksTabContentProps): React.ReactElement {
  const { decks, isLoading, error, reload } = useDecks();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete(deckId: string): Promise<void> {
    setDeletingId(deckId);
    setDeleteError(null);
    try {
      await deleteDeck(deckId);
      reload();
      onDecksChanged();
    } catch {
      setDeleteError("No se pudo eliminar el deck. Intenta de nuevo.");
    } finally {
      setDeletingId(null);
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <div className="w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-5 rounded-2xl bg-red-900/30 border border-red-700/50 text-red-300 text-sm">
        {error}
        <button
          type="button"
          onClick={reload}
          className="mt-3 block px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-xl"
        >
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Botón crear */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onCreateDeck}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold rounded-xl transition-colors"
        >
          + Crear Deck
        </button>
      </div>

      {/* Error de eliminación */}
      {deleteError && (
        <div className="p-3 rounded-xl bg-red-900/30 border border-red-700/50 text-red-300 text-xs">
          {deleteError}
        </div>
      )}

      {/* Lista */}
      {decks.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <p className="text-lg font-semibold">Aún no tienes decks</p>
          <p className="text-sm mt-1">Crea tu primer deck con 12 cartas de tu colección.</p>
          <button
            type="button"
            onClick={onCreateDeck}
            className="mt-4 px-6 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold rounded-xl transition-colors"
          >
            + Crear Deck
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {decks.map((deck) => (
            <div
              key={deck.id}
              className="flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-900/80 border border-arena-border"
            >
              <span className="font-semibold text-white truncate flex-1">{deck.name}</span>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  disabled={deletingId === deck.id}
                  onClick={() => onEditDeck(deck.id)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-slate-200 transition-colors"
                >
                  Editar
                </button>
                <button
                  type="button"
                  disabled={deletingId === deck.id}
                  onClick={() => void handleDelete(deck.id)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-900/50 hover:bg-red-700/70 disabled:opacity-40 text-red-300 hover:text-white transition-colors"
                >
                  {deletingId === deck.id ? "..." : "Eliminar"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
