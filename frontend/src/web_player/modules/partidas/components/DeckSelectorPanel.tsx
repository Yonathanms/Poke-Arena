/** Selector de mazos propios de 12 cartas para entrar en cola de Arena. */

import React from "react";
import { CheckCircle2, Layers, PlusCircle } from "lucide-react";
import { DECK_SIZE, type DeckSummary } from "../../decks/types/deck.types";

export interface DeckSelectorPanelProps {
  readonly decks: readonly DeckSummary[];
  readonly selectedDeckId: string | null;
  readonly isLoading?: boolean;
  readonly disabled?: boolean;
  readonly onSelectDeck: (deckId: string) => void;
  readonly onCreateDeck: () => void;
}

export function DeckSelectorPanel({
  decks,
  selectedDeckId,
  isLoading = false,
  disabled = false,
  onSelectDeck,
  onCreateDeck,
}: DeckSelectorPanelProps): React.ReactElement {
  const validDecks = decks.filter((deck) => deck.card_count === DECK_SIZE);

  if (isLoading) {
    return (
      <div className="glass-card p-6 flex items-center justify-center gap-3 text-slate-300 text-sm">
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span>Cargando tus mazos preparados...</span>
      </div>
    );
  }

  if (validDecks.length === 0) {
    return (
      <div className="glass-card p-6 text-center flex flex-col items-center gap-3">
        <div className="w-12 h-12 rounded-2xl bg-[#090D16]/90 border border-white/10 flex items-center justify-center text-blue-400">
          <Layers className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-base font-bold text-white">Necesitas un mazo de 12 cartas</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-md">
            Para desafiar a otros entrenadores en la Arena debes armar al menos un mazo completo
            con 12 cartas distintas de tu colección.
          </p>
        </div>
        <button
          type="button"
          onClick={onCreateDeck}
          className="mt-1 inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99]"
        >
          <PlusCircle className="w-4 h-4" />
          <span>Crear mi primer Deck</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
          Elige tu mazo de combate
        </span>
        <span className="text-[11px] text-slate-400">
          {validDecks.length} {validDecks.length === 1 ? "mazo listo" : "mazos listos"}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {validDecks.map((deck) => {
          const selected = deck.id === selectedDeckId;
          return (
            <button
              key={deck.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelectDeck(deck.id)}
              className={`text-left rounded-xl p-4 border transition-all duration-200 flex items-center justify-between gap-3 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                selected
                  ? "bg-blue-500/15 border-blue-500/80 shadow-lg shadow-blue-600/15"
                  : "bg-[#090D16]/90 border-white/10 hover:border-blue-400/40 hover:bg-[#090D16]"
              }`}
            >
              <div className="min-w-0 flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center border shrink-0 ${
                    selected
                      ? "bg-blue-500/25 border-blue-400/60 text-blue-300"
                      : "bg-slate-800/80 border-white/10 text-slate-400"
                  }`}
                >
                  <Layers className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-white truncate">{deck.name}</p>
                  <p className="text-[11px] text-emerald-400 font-medium mt-0.5">
                    {deck.card_count} cartas listas
                  </p>
                </div>
              </div>

              {selected && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-500/20 border border-blue-400/50 text-blue-200 text-[11px] font-bold shrink-0">
                  <CheckCircle2 className="w-3.5 h-3.5 text-blue-400" />
                  <span>Elegido</span>
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
