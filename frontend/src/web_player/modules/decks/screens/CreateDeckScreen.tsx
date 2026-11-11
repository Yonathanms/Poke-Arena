import React, { useEffect, useState } from "react";
import { useCardThumbnail } from "../../catalogo/hooks/useCardThumbnail";
import { useCreateDeck } from "../hooks/useCreateDeck";
import { getPlayerCards } from "../services/collection.api";
import type { PlayerCard } from "../types/deck.types";
import { DECK_SIZE } from "../types/deck.types";

const RARITY_HOVER_GLOW: Record<string, string> = {
  COMUN: "hover:shadow-[0_0_15px_rgba(148,163,184,0.25)] hover:border-slate-400/40",
  POCO_COMUN: "hover:shadow-[0_0_18px_rgba(180,83,9,0.35)] hover:border-amber-600/50",
  RARA: "hover:shadow-[0_0_20px_rgba(56,189,248,0.4)] hover:border-sky-400/60",
  LEGENDARIA: "hover:shadow-[0_0_25px_rgba(234,179,8,0.5)] hover:border-yellow-400/70",
};

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

interface CreateDeckScreenProps {
  readonly onBack: () => void;
  readonly onSuccess: () => void;
}

export function CreateDeckScreen({ onBack, onSuccess }: CreateDeckScreenProps): React.ReactElement {
  const [cards, setCards] = useState<PlayerCard[]>([]);
  const [cardsLoading, setCardsLoading] = useState(true);
  const [cardsError, setCardsError] = useState<string | null>(null);

  const {
    name, selectedCardIds, status, errorMessage,
    setName, toggleCard, isCardSelected, canSubmit, submit,
  } = useCreateDeck(() => onSuccess());

  useEffect(() => {
    setCardsLoading(true);
    getPlayerCards()
      .then(setCards)
      .catch(() => setCardsError("No se pudo cargar tu colección."))
      .finally(() => setCardsLoading(false));
  }, []);

  const cardById = new Map(cards.map((c) => [c.id, c]));
  const availableCards = cards.filter((c) => !isCardSelected(c.id));

  return (
    <div className="min-h-screen poke-arena-bg text-slate-100 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto flex flex-col gap-6 glass-card p-6 sm:p-8">

        {/* Cabecera */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onBack}
            className="bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl p-2.5 transition-all"
            aria-label="Volver"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-extrabold text-white">Crear Deck</h1>
            <p className="text-xs text-slate-400">Selecciona exactamente 12 cartas de tu colección</p>
          </div>
        </div>

        {/* Nombre */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
            Nombre del Deck
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            placeholder="Mi deck favorito"
            className="w-full bg-[#090D16]/90 border border-white/10 rounded-xl px-3.5 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all text-sm"
          />
        </div>

        {/* 12 slots del deck */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Cartas del deck
            </span>
            <span className={`text-xs font-bold ${selectedCardIds.length === DECK_SIZE ? "text-emerald-400" : "text-slate-400"}`}>
              {selectedCardIds.length}/{DECK_SIZE}
            </span>
          </div>
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2.5">
            {Array.from({ length: DECK_SIZE }).map((_, i) => {
              const cardId = selectedCardIds[i];
              const card = cardId ? cardById.get(cardId) : undefined;
              const rarityGlow = card ? (RARITY_HOVER_GLOW[card.rarity] ?? RARITY_HOVER_GLOW.COMUN) : "";
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => cardId && toggleCard(cardId)}
                  disabled={!cardId}
                  title={card ? `Quitar ${card.name}` : "Espacio vacío"}
                  className={[
                    "relative rounded-xl overflow-hidden border transition-all duration-300",
                    "aspect-[5/7]",
                    card
                      ? `border-blue-500/60 hover:-translate-y-1 cursor-pointer ${rarityGlow}`
                      : "border-dashed border-white/15 bg-[#090D16]/60 cursor-default",
                  ].join(" ")}
                >
                  {card ? (
                    <>
                      <CardThumb id={card.id} name={card.name} className="w-full h-full" />
                      {/* overlay al hover para indicar "quitar" */}
                      <div className="absolute inset-0 bg-red-900/0 hover:bg-red-900/40 transition-colors flex items-center justify-center opacity-0 hover:opacity-100">
                        <span className="text-white text-xs font-bold">✕</span>
                      </div>
                    </>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-slate-600 text-lg font-bold">{i + 1}</span>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Separador */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-white/10" />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Cartas disponibles
          </span>
          <div className="flex-1 h-px bg-white/10" />
        </div>

        {/* Grid de cartas disponibles */}
        {cardsLoading ? (
          <div className="flex justify-center py-10">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : cardsError ? (
          <div className="p-4 rounded-xl bg-slate-800/60 border border-white/10 text-slate-400 text-sm text-center">
            <p className="font-semibold text-slate-300 mb-1">Vista de cartas no disponible aún</p>
            <p className="text-xs">La selección de cartas se habilitará cuando se implemente el catálogo de colección.</p>
          </div>
        ) : availableCards.length === 0 && selectedCardIds.length < DECK_SIZE ? (
          <p className="text-center text-slate-400 text-sm py-6">Tu colección está vacía.</p>
        ) : availableCards.length === 0 ? (
          <p className="text-center text-emerald-400 text-sm py-6">✓ Deck completo</p>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2.5">
            {availableCards.map((card) => {
              const rarityGlow = RARITY_HOVER_GLOW[card.rarity] ?? RARITY_HOVER_GLOW.COMUN;
              return (
                <button
                  key={card.id}
                  type="button"
                  onClick={() => toggleCard(card.id)}
                  disabled={selectedCardIds.length >= DECK_SIZE}
                  title={card.name}
                  className={[
                    "relative rounded-xl overflow-hidden border aspect-[5/7] transition-all duration-300",
                    selectedCardIds.length >= DECK_SIZE
                      ? "border-slate-800 opacity-40 cursor-not-allowed"
                      : `border-white/15 hover:-translate-y-1 cursor-pointer ${rarityGlow}`,
                  ].join(" ")}
                >
                  <CardThumb id={card.id} name={card.name} className="w-full h-full" />
                  <div className="absolute inset-0 hover:bg-blue-500/10 transition-colors" />
                </button>
              );
            })}
          </div>
        )}

        {/* Error submit */}
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
          className="w-full bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-3 shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99] disabled:bg-slate-700 disabled:from-slate-700 disabled:to-slate-700 disabled:border-slate-600 disabled:shadow-none disabled:cursor-not-allowed"
        >
          {status === "submitting" ? "Creando deck..." : "Crear Deck"}
        </button>
      </div>
    </div>
  );
}
