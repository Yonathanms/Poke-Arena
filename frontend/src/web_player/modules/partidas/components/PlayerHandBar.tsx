/** Barra inferior del jugador: Energía del turno, Mazo restante, Cementerio y Mano de cartas. */

import React, { useState } from "react";
import { Flame, Layers, Skull, Sparkles, X, Zap } from "lucide-react";
import { useCardImage } from "../../catalogo/hooks/useCardThumbnail";
import type { MatchCardDTO, MatchEnergyDTO } from "../types/partidas.types";

export interface PlayerHandBarProps {
  readonly hand: readonly MatchCardDTO[];
  readonly deckRemaining: number;
  readonly graveyardCount: number;
  readonly energy: MatchEnergyDTO;
}

const RARITY_STYLES: Readonly<
  Record<string, { label: string; border: string; glow: string; badge: string }>
> = {
  COMUN: {
    label: "Común",
    border: "border-slate-400/35",
    glow: "hover:shadow-[0_0_16px_rgba(148,163,184,0.28)] hover:border-slate-300/60",
    badge: "text-slate-300 border-slate-500/50 bg-slate-800/60",
  },
  POCO_COMUN: {
    label: "Poco Común",
    border: "border-amber-600/50",
    glow: "hover:shadow-[0_0_18px_rgba(180,83,9,0.38)] hover:border-amber-500/70",
    badge: "text-amber-300 border-amber-600/50 bg-amber-950/40",
  },
  RARA: {
    label: "Rara",
    border: "border-sky-400/55",
    glow: "hover:shadow-[0_0_20px_rgba(56,189,248,0.42)] hover:border-sky-300/80",
    badge: "text-sky-300 border-sky-500/50 bg-sky-950/40",
  },
  LEGENDARIA: {
    label: "Legendaria",
    border: "border-yellow-400/65",
    glow: "hover:shadow-[0_0_24px_rgba(234,179,8,0.5)] hover:border-yellow-300/85",
    badge: "text-yellow-300 border-yellow-400/60 bg-yellow-950/45 font-bold",
  },
};

function HandCardTile({
  card,
  energyAvailable,
  onInspect,
}: {
  readonly card: MatchCardDTO;
  readonly energyAvailable: number;
  readonly onInspect: (card: MatchCardDTO) => void;
}): React.ReactElement {
  const imageUrl = useCardImage(card.id);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const rarity = RARITY_STYLES[card.rarity] ?? RARITY_STYLES.COMUN;
  const playableWithEnergy = card.cost <= energyAvailable;

  return (
    <button
      type="button"
      onClick={() => onInspect(card)}
      className={`group text-left rounded-2xl p-2.5 bg-[#0F172A]/90 backdrop-blur-md border transition-all duration-300 hover:-translate-y-2 shadow-lg flex flex-col cursor-pointer ${rarity.border} ${rarity.glow}`}
    >
      <div className="relative aspect-[5/7] w-full rounded-xl overflow-hidden border border-white/10 bg-[#090D16]/90 flex items-center justify-center">
        {imageUrl && imageUrl !== failedUrl ? (
          <img
            src={imageUrl}
            alt={card.name}
            onError={() => setFailedUrl(imageUrl)}
            className="w-full h-full object-contain p-1 transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-2 text-center">
            <Sparkles className="w-6 h-6 text-slate-500 mb-1" />
            <span className="text-[11px] font-semibold text-slate-300 line-clamp-2">
              {card.name}
            </span>
          </div>
        )}

        {/* Costo de energía */}
        <div
          className={`absolute top-1.5 left-1.5 w-7 h-7 rounded-full border flex items-center justify-center shadow-md backdrop-blur-sm text-xs font-black ${
            playableWithEnergy
              ? "bg-slate-950/90 border-amber-400/80 text-amber-300"
              : "bg-slate-950/90 border-slate-600 text-slate-400"
          }`}
          title={`Costo: ${card.cost}`}
        >
          {card.cost}
        </div>

        {/* Poder */}
        <div
          className="absolute bottom-1.5 right-1.5 px-2 py-0.5 rounded-md bg-slate-950/90 border border-emerald-400/50 text-emerald-300 text-[11px] font-extrabold shadow-md"
          title={`Poder: ${card.power}`}
        >
          {card.power} POD
        </div>
      </div>

      <div className="mt-2 flex flex-col gap-0.5 min-w-0">
        <div className="flex items-center justify-between gap-1">
          <span className="text-[10px] font-mono text-slate-400 truncate">{card.code}</span>
          <span className={`text-[9px] px-1.5 py-0.2 rounded border shrink-0 ${rarity.badge}`}>
            {rarity.label}
          </span>
        </div>
        <p className="text-xs font-bold text-white truncate group-hover:text-blue-400 transition-colors">
          {card.name}
        </p>
        <p className="text-[10px] text-slate-400 truncate flex items-center gap-1">
          <Flame className="w-3 h-3 text-amber-400 shrink-0" />
          <span className="truncate">{card.ability_name}</span>
        </p>
      </div>
    </button>
  );
}

export function PlayerHandBar({
  hand,
  deckRemaining,
  graveyardCount,
  energy,
}: PlayerHandBarProps): React.ReactElement {
  const [inspectedCard, setInspectedCard] = useState<MatchCardDTO | null>(null);
  const inspectedImageUrl = useCardImage(inspectedCard?.id ?? "");

  return (
    <>
      <div className="glass-card p-4 sm:p-5 flex flex-col lg:flex-row items-stretch gap-5">
        {/* Panel lateral izquierdo: Energía y pilas de mazo / cementerio */}
        <div className="flex flex-row lg:flex-col justify-between gap-3 lg:w-52 shrink-0">
          <div className="bg-[#090D16]/90 border border-amber-400/35 rounded-xl p-3.5 flex-1 flex flex-col justify-center">
            <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-amber-300/80">
              <Zap className="w-4 h-4 text-amber-400" />
              <span>Energía del turno</span>
            </div>
            <p className="text-2xl font-extrabold text-amber-400 mt-1">{energy.total}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Base {energy.base} + Bono {energy.bonus}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2.5 flex-1">
            <div
              className="bg-[#090D16]/90 border border-white/10 rounded-xl p-3 flex flex-col justify-center"
              title="Cartas restantes en tu mazo"
            >
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                <span>Mazo</span>
              </div>
              <p className="text-lg font-extrabold text-white mt-0.5">{deckRemaining}</p>
            </div>

            <div
              className="bg-[#090D16]/90 border border-white/10 rounded-xl p-3 flex flex-col justify-center"
              title="Cartas en tu cementerio"
            >
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                <Skull className="w-3.5 h-3.5 text-slate-400" />
                <span>Cement.</span>
              </div>
              <p className="text-lg font-extrabold text-slate-200 mt-0.5">{graveyardCount}</p>
            </div>
          </div>
        </div>

        {/* Mano del jugador */}
        <div className="flex-1 flex flex-col gap-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Tu mano ({hand.length} {hand.length === 1 ? "carta" : "cartas"})
            </span>
            <span className="text-[11px] text-slate-400">
              Haz clic en una carta para ver su detalle
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {hand.map((card) => (
              <HandCardTile
                key={card.id}
                card={card}
                energyAvailable={energy.total}
                onInspect={setInspectedCard}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Modal rápido de inspección de carta en mano */}
      {inspectedCard && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setInspectedCard(null)}
        >
          <div
            className="glass-card max-w-md w-full p-5 flex flex-col gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-mono text-slate-400">{inspectedCard.code}</p>
                <h3 className="text-lg font-extrabold text-white">{inspectedCard.name}</h3>
              </div>
              <button
                type="button"
                onClick={() => setInspectedCard(null)}
                className="bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl p-2 transition-all"
                aria-label="Cerrar detalle"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {inspectedImageUrl && (
              <div className="aspect-[5/7] w-48 mx-auto rounded-xl overflow-hidden border border-white/10 bg-[#090D16]/90">
                <img
                  src={inspectedImageUrl}
                  alt={inspectedCard.name}
                  className="w-full h-full object-contain"
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-2.5 text-xs">
              <div className="bg-[#090D16]/90 border border-white/10 rounded-xl p-3">
                <span className="text-slate-400">Costo de energía</span>
                <p className="text-base font-extrabold text-amber-400 mt-0.5">
                  {inspectedCard.cost}
                </p>
              </div>
              <div className="bg-[#090D16]/90 border border-white/10 rounded-xl p-3">
                <span className="text-slate-400">Poder base</span>
                <p className="text-base font-extrabold text-emerald-400 mt-0.5">
                  {inspectedCard.power}
                </p>
              </div>
            </div>

            <div className="bg-[#090D16]/90 border border-white/10 rounded-xl p-3">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Habilidad
              </span>
              <p className="text-sm font-semibold text-white mt-0.5">
                {inspectedCard.ability_name}
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
