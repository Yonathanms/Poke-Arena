/** Pantalla de listado de decks del jugador. */

import React, { useState } from "react";
import { deleteDeck } from "../services/decks.api";
import { useDecks } from "../hooks/useDecks";

interface MyDecksScreenProps {
  readonly onBack: () => void;
  readonly onCreateDeck: () => void;
  readonly onEditDeck: (deckId: string) => void;
}

export function MyDecksScreen({ onBack, onCreateDeck, onEditDeck }: MyDecksScreenProps): React.ReactElement {
  const { decks, isLoading, error, reload } = useDecks();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete(deckId: string): Promise<void> {
    setDeletingId(deckId);
    setDeleteError(null);
    try {
      await deleteDeck(deckId);
      reload();
    } catch {
      setDeleteError("No se pudo eliminar el deck. Intenta de nuevo.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto flex flex-col gap-6">
        {/* Cabecera */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onBack}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            aria-label="Volver"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-extrabold text-white">Mis Decks</h1>
            <p className="text-xs text-slate-400">Administra tus mazos de batalla</p>
          </div>
          <div className="ml-auto">
            <button
              type="button"
              onClick={onCreateDeck}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold rounded-xl transition-colors"
            >
              + Crear Deck
            </button>
          </div>
        </div>

        {/* Contenido */}
        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
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
        ) : decks.length === 0 ? (
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
            {deleteError && (
              <div className="p-3 rounded-xl bg-red-900/30 border border-red-700/50 text-red-300 text-xs">
                {deleteError}
              </div>
            )}
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
    </div>
  );
}
