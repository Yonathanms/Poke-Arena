import React from "react";

interface DeckStatsCardProps {
  readonly deckCount: number;
  readonly isLoading: boolean;
  readonly onClick: () => void;
}

export function DeckStatsCard({ deckCount, isLoading, onClick }: DeckStatsCardProps): React.ReactElement {
  return (
    <button
      type="button"
      onClick={onClick}
      className="p-5 rounded-2xl bg-slate-900/80 border border-arena-border shadow-lg text-left w-full hover:border-violet-500/50 transition-colors cursor-pointer"
    >
      <div className="flex items-center justify-between text-slate-400 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider">Mis Decks</span>
        <span className="p-1.5 rounded-lg bg-violet-500/10 text-violet-400">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </span>
      </div>
      {isLoading ? (
        <div className="text-2xl font-extrabold text-slate-500 animate-pulse">—</div>
      ) : (
        <div className="text-2xl font-extrabold text-white">
          {deckCount}{" "}
          <span className="text-sm font-normal text-slate-400">
            {deckCount === 1 ? "deck" : "decks"}
          </span>
        </div>
      )}
      <p className="text-[11px] text-slate-500 mt-1">Crea y edita tus decks</p>
    </button>
  );
}
