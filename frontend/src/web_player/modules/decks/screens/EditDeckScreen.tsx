import React, { useEffect, useState } from "react";
import { useCardThumbnail } from "../../catalogo/hooks/useCardThumbnail";
import { useEditDeck } from "../hooks/useEditDeck";
import { getDeck } from "../services/decks.api";
import { getPlayerCards } from "../services/collection.api";
import type { PlayerCard } from "../types/deck.types";
import { DECK_SIZE } from "../types/deck.types";

function CardThumb({ id, name, className }: { id: string; name: string; className?: string }): React.ReactElement {
  const url = useCardThumbnail(id);
  if (!url) {
    return (
      <div className={`flex items-end p-1 bg-slate-800 ${className ?? ""}`}>
        <span className="text-[9px] text-slate-300 font-semibold truncate w-full text-center">{name}</span>
      </div>
    );
  }
  return <img src={url} alt={name} className={`object-cover ${className ?? ""}`} />;
}

interface EditDeckScreenProps {
  readonly deckId: string;
  readonly onBack: () => void;
  readonly onSuccess: () => void;
}

export function EditDeckScreen({ deckId, onBack, onSuccess }: EditDeckScreenProps): React.ReactElement {
  const [initialName, setInitialName] = useState<string | null>(null);
  const [initialCardIds, setInitialCardIds] = useState<string[] | null>(null);
  const [cards, setCards] = useState<PlayerCard[]>([]);
  const [loadingDeck, setLoadingDeck] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    setLoadingDeck(true);
    Promise.all([getDeck(deckId), getPlayerCards()])
      .then(([deck, playerCards]) => {
        setInitialName(deck.name);
        setInitialCardIds(deck.card_ids);
        setCards(playerCards);
      })
      .catch(() => setLoadError("No se pudo cargar el deck."))
      .finally(() => setLoadingDeck(false));
  }, [deckId]);

  if (loadingDeck) {
    return (
      <div className="min-h-screen bg-arena-bg text-slate-100 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (loadError || initialName === null || initialCardIds === null) {
    return (
      <div className="min-h-screen bg-arena-bg text-slate-100 flex items-center justify-center">
        <p className="text-red-400">{loadError ?? "Error inesperado."}</p>
      </div>
    );
  }

  return (
    <EditDeckForm
      deckId={deckId}
      initialName={initialName}
      initialCardIds={initialCardIds}
      cards={cards}
      onBack={onBack}
      onSuccess={onSuccess}
    />
  );
}

interface EditDeckFormProps {
  readonly deckId: string;
  readonly initialName: string;
  readonly initialCardIds: string[];
  readonly cards: PlayerCard[];
  readonly onBack: () => void;
  readonly onSuccess: () => void;
}

function EditDeckForm({ deckId, initialName, initialCardIds, cards, onBack, onSuccess }: EditDeckFormProps): React.ReactElement {
  const {
    name, selectedCardIds, status, errorMessage,
    setName, toggleCard, isCardSelected, canSubmit, submit,
  } = useEditDeck(deckId, initialName, initialCardIds, () => onSuccess());

  const cardById = new Map(cards.map((c) => [c.id, c]));
  const availableCards = cards.filter((c) => !isCardSelected(c.id));

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
            <h1 className="text-2xl font-extrabold text-white">Editar Deck</h1>
            <p className="text-xs text-slate-400">Modifica el nombre o las cartas del deck</p>
          </div>
        </div>

        {/* Nombre */}
        <div>
          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Nombre del Deck
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            placeholder="Nombre del deck"
            className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 focus:border-violet-500 outline-none rounded-xl text-white text-sm placeholder:text-slate-500 transition-colors"
          />
        </div>

        {/* 12 slots */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Cartas del deck</span>
            <span className={`text-xs font-semibold ${selectedCardIds.length === DECK_SIZE ? "text-emerald-400" : "text-slate-500"}`}>
              {selectedCardIds.length}/{DECK_SIZE}
            </span>
          </div>
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
            {Array.from({ length: DECK_SIZE }).map((_, i) => {
              const cardId = selectedCardIds[i];
              const card = cardId ? cardById.get(cardId) : undefined;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => cardId && toggleCard(cardId)}
                  disabled={!cardId}
                  title={card ? `Quitar ${card.name}` : "Espacio vacío"}
                  className={[
                    "relative rounded-xl overflow-hidden border transition-all aspect-[5/7]",
                    card
                      ? "border-violet-500/70 hover:border-red-400/70 cursor-pointer"
                      : "border-dashed border-slate-700 cursor-default",
                  ].join(" ")}
                >
                  {card ? (
                    <>
                      <CardThumb id={card.id} name={card.name} className="w-full h-full" />
                      <div className="absolute inset-0 bg-red-900/0 hover:bg-red-900/40 transition-colors flex items-center justify-center opacity-0 hover:opacity-100">
                        <span className="text-white text-xs font-bold">✕</span>
                      </div>
                    </>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-slate-700 text-lg font-bold">{i + 1}</span>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Separador */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-slate-700" />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Cartas disponibles</span>
          <div className="flex-1 h-px bg-slate-700" />
        </div>

        {/* Grid de cartas disponibles */}
        {availableCards.length === 0 && selectedCardIds.length < DECK_SIZE ? (
          <p className="text-center text-slate-500 text-sm py-6">Tu colección está vacía.</p>
        ) : availableCards.length === 0 ? (
          <p className="text-center text-emerald-400 text-sm py-6">✓ Deck completo</p>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
            {availableCards.map((card) => (
              <button
                key={card.id}
                type="button"
                onClick={() => toggleCard(card.id)}
                disabled={selectedCardIds.length >= DECK_SIZE}
                title={card.name}
                className={[
                  "relative rounded-xl overflow-hidden border aspect-[5/7] transition-all",
                  selectedCardIds.length >= DECK_SIZE
                    ? "border-slate-800 opacity-40 cursor-not-allowed"
                    : "border-slate-700 hover:border-violet-500/70 cursor-pointer",
                ].join(" ")}
              >
                <CardThumb id={card.id} name={card.name} className="w-full h-full" />
                <div className="absolute inset-0 hover:bg-violet-500/10 transition-colors" />
              </button>
            ))}
          </div>
        )}

        {/* Error */}
        {errorMessage && (
          <div className="p-4 rounded-xl bg-red-900/30 border border-red-700/50 text-red-300 text-sm">
            {errorMessage}
          </div>
        )}

        {/* Botón */}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!canSubmit || status === "submitting"}
          className="w-full py-3 bg-violet-600 hover:bg-violet-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
        >
          {status === "submitting" ? "Guardando..." : "Guardar Cambios"}
        </button>
      </div>
    </div>
  );
}
