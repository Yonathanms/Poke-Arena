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
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
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
          className="mt-3 block bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-4 py-2 text-xs font-semibold transition-all"
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
          className="bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99]"
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
        <div className="glass-card text-center py-16 px-6 text-slate-400">
          <p className="text-lg font-bold text-white">Aún no tienes decks</p>
          <p className="text-sm mt-1">Crea tu primer deck con 12 cartas de tu colección.</p>
          <button
            type="button"
            onClick={onCreateDeck}
            className="mt-4 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-6 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99]"
          >
            + Crear Deck
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {decks.map((deck) => (
            <div
              key={deck.id}
              className="flex items-center gap-3 px-5 py-3.5 glass-card"
            >
              <span className="font-semibold text-white truncate flex-1">{deck.name}</span>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  disabled={deletingId === deck.id}
                  onClick={() => onEditDeck(deck.id)}
                  className="bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all disabled:opacity-40"
                >
                  Editar
                </button>
                <button
                  type="button"
                  disabled={deletingId === deck.id}
                  onClick={() => void handleDelete(deck.id)}
                  className="px-3.5 py-1.5 text-xs font-semibold rounded-xl border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 disabled:opacity-40 text-red-200 transition-all"
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
