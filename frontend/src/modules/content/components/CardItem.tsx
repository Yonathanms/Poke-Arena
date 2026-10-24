import React from "react";
import { Zap } from "lucide-react";
import { AbilitySummaryDTO, CardDTO, CardType } from "../types/content";

interface CardItemProps {
  card: CardDTO;
}

const TYPE_COLORS: Record<CardType, { bg: string; text: string; border: string; glow: string }> = {
  FUE: { bg: "bg-red-500/20", text: "text-red-400", border: "border-red-500/40", glow: "hover:shadow-red-500/20" },
  AGU: { bg: "bg-blue-500/20", text: "text-blue-400", border: "border-blue-500/40", glow: "hover:shadow-blue-500/20" },
  PLA: { bg: "bg-emerald-500/20", text: "text-emerald-400", border: "border-emerald-500/40", glow: "hover:shadow-emerald-500/20" },
  ELE: { bg: "bg-amber-500/20", text: "text-amber-400", border: "border-amber-500/40", glow: "hover:shadow-amber-500/20" },
  PSI: { bg: "bg-purple-500/20", text: "text-purple-400", border: "border-purple-500/40", glow: "hover:shadow-purple-500/20" },
  LUC: { bg: "bg-orange-600/20", text: "text-orange-400", border: "border-orange-600/40", glow: "hover:shadow-orange-600/20" },
};

const RARITY_COLORS: Record<string, string> = {
  COMUN: "text-slate-400 border-slate-600/40",
  POCO_COMUN: "text-emerald-400 border-emerald-500/40",
  RARA: "text-blue-400 border-blue-500/40",
  LEGENDARIA: "text-amber-400 border-amber-500/40 shadow-amber-500/10",
};

export const CardItem: React.FC<CardItemProps> = ({ card }) => {
  const typeStyle = TYPE_COLORS[card.card_type];
  const rarityStyle = RARITY_COLORS[card.rarity] || RARITY_COLORS.COMUN;
  const abilityIsSummary = (
    ability: NonNullable<CardDTO["ability"]>
  ): ability is AbilitySummaryDTO => "trigger" in ability;
  const abilityTrigger = card.ability
    ? abilityIsSummary(card.ability)
      ? card.ability.trigger
      : card.ability.ability_type
    : null;
  const abilityEffect = card.ability
    ? abilityIsSummary(card.ability)
      ? card.ability.effect
      : card.ability.description
    : null;

  return (
    <div
      className={`group relative flex flex-col rounded-2xl glass-card overflow-hidden transition-all duration-300 hover:-translate-y-1.5 hover:shadow-2xl ${typeStyle.glow}`}
    >
      {/* Aspect Ratio 5:7 Container */}
      <div className="relative w-full aspect-[5/7] bg-arena-surface overflow-hidden">
        {card.thumbnail_url || card.image_url ? (
          <img
            src={card.thumbnail_url || card.image_url || ""}
            alt={card.name}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center text-slate-400">
            <span className="text-4xl" aria-hidden="true">◉</span>
            <span className="text-xs font-medium">Sin imagen</span>
          </div>
        )}

        {/* Top Badges (Cost and Power) */}
        <div className="absolute top-2.5 left-2.5 flex items-center justify-center w-8 h-8 rounded-full bg-blue-600/90 text-white font-extrabold text-sm shadow-md backdrop-blur-sm border border-blue-400/50">
          {card.cost}
        </div>

        <div className="absolute top-2.5 right-2.5 flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-900/90 text-amber-400 font-bold text-xs shadow-md backdrop-blur-sm border border-amber-500/40">
          <Zap className="w-3 h-3 fill-amber-400" />
          <span>{card.power}</span>
        </div>

        {/* Element Pill Bottom-Left */}
        <div
          className={`absolute bottom-2.5 left-2.5 px-2.5 py-0.5 rounded-md text-xs font-bold border backdrop-blur-md ${typeStyle.bg} ${typeStyle.text} ${typeStyle.border}`}
        >
          {card.card_type}
        </div>

        {/* Code Bottom-Right */}
        <div className="absolute bottom-2.5 right-2.5 px-2 py-0.5 rounded text-[10px] font-mono bg-black/60 text-slate-300 backdrop-blur-sm">
          {card.code}
        </div>
      </div>

      {/* Card Body & Details */}
      <div className="p-3.5 flex flex-col gap-1.5 flex-1 justify-between bg-arena-card/90">
        <div>
          <div className="flex items-center justify-between gap-1">
            <h3 className="font-bold text-slate-100 text-sm truncate">{card.name}</h3>
            <span className={`text-[10px] px-1.5 py-0.2 rounded border font-semibold ${rarityStyle}`}>
              {card.rarity}
            </span>
          </div>

          {/* Ability snippet */}
          {card.ability && abilityTrigger && abilityTrigger !== "HAB-000" && (
            <div className="mt-2 text-xs bg-arena-surface/80 rounded-lg p-2 border border-arena-border/50">
              <span className="text-blue-400 font-semibold block text-[11px]">
                ✦ {abilityTrigger}
              </span>
              {abilityEffect && (
                <p className="text-slate-300 text-[11px] line-clamp-2 mt-0.5">
                  {abilityEffect}
                </p>
              )}
              {abilityIsSummary(card.ability) && card.ability.affected_card_type && (
                <span className="mt-1 block text-[10px] text-slate-400">
                  Afecta tipo {card.ability.affected_card_type}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
