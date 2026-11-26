/**
 * Tarjeta visual de una carta asignada en el paquete inicial (US 3.1.1).
 *
 * Muestra la imagen real 5:7 de la carta servida desde MongoDB GridFS
 * (`/api/v1/content/cards/{id}/image`) junto con sus atributos autoritativos
 * (costo, poder, tipo elemental, código, rareza y habilidad).
 */

import React, { useState } from "react";
import { CheckCircle, Flame, Sparkles, Zap } from "lucide-react";
import { useCardImage } from "../../catalogo/hooks/useCardThumbnail";
import type { InitialPackCardDTO } from "../types/initial_pack.types";

export interface InitialPackCardTileProps {
  readonly card: InitialPackCardDTO;
  readonly className?: string;
}

interface ElementBadgeStyle {
  readonly label: string;
  readonly badgeClass: string;
  readonly borderClass: string;
}

const ELEMENT_STYLES: Record<string, ElementBadgeStyle> = {
  FUE: {
    label: "Fuego",
    badgeClass: "bg-red-500/20 text-red-300 border-red-500/40",
    borderClass: "border-orange-500/40 hover:border-orange-400/70",
  },
  AGU: {
    label: "Agua",
    badgeClass: "bg-blue-500/20 text-blue-300 border-blue-500/40",
    borderClass: "border-blue-500/40 hover:border-blue-400/70",
  },
  PLA: {
    label: "Planta",
    badgeClass: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    borderClass: "border-emerald-500/40 hover:border-emerald-400/70",
  },
  ELE: {
    label: "Eléctrico",
    badgeClass: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    borderClass: "border-amber-500/40 hover:border-amber-400/70",
  },
  PSI: {
    label: "Psíquico",
    badgeClass: "bg-purple-500/20 text-purple-300 border-purple-500/40",
    borderClass: "border-purple-500/40 hover:border-purple-400/70",
  },
  LUC: {
    label: "Lucha",
    badgeClass: "bg-orange-500/20 text-orange-300 border-orange-500/40",
    borderClass: "border-amber-700/40 hover:border-amber-500/70",
  },
};

const DEFAULT_STYLE: ElementBadgeStyle = {
  label: "Normal",
  badgeClass: "bg-slate-600/25 text-slate-300 border-slate-500/40",
  borderClass: "border-slate-700 hover:border-slate-500",
};

export function InitialPackCardTile({
  card,
  className = "",
}: InitialPackCardTileProps): React.ReactElement {
  const imageUrl = useCardImage(card.id);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const style = ELEMENT_STYLES[card.card_type.toUpperCase()] ?? DEFAULT_STYLE;

  return (
    <article
      tabIndex={0}
      aria-label={`${card.name} (${card.code}) - Tipo ${style.label}, Costo ${card.cost}, Poder ${card.power}`}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border bg-[#0F172A]/85 p-2.5 shadow-lg backdrop-blur-md transition-all duration-200 hover:-translate-y-1 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${style.borderClass} ${className}`}
    >
      {/* Imagen real 5:7 desde GridFS */}
      <div className="relative aspect-[5/7] w-full overflow-hidden rounded-xl border border-white/10 bg-slate-900 flex items-center justify-center">
        {imageUrl && imageUrl !== failedUrl ? (
          <img
            src={imageUrl}
            alt={card.name}
            onError={() => setFailedUrl(imageUrl)}
            className="h-full w-full object-contain p-0.5 transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-4 text-center animate-pulse">
            <Sparkles className="mb-2 h-7 w-7 text-slate-500" aria-hidden="true" />
            <span className="text-xs font-semibold text-slate-400">{card.name}</span>
            <span className="font-mono text-[10px] text-slate-500">{card.code}</span>
          </div>
        )}

        {/* Costo de energía */}
        <div
          className="absolute left-2 top-2 flex h-7 w-7 items-center justify-center rounded-full border border-amber-400/80 bg-slate-950/85 text-amber-300 shadow-md backdrop-blur-sm"
          title={`Costo de energía: ${card.cost}`}
        >
          <span className="text-xs font-black">{card.cost}</span>
        </div>

        {/* Tipo elemental */}
        <div
          className={`absolute right-2 top-2 rounded-full border px-2 py-0.5 text-[10px] font-bold backdrop-blur-sm ${style.badgeClass}`}
        >
          {style.label}
        </div>

        {/* Cantidad asignada */}
        <div className="absolute bottom-2 right-2 backdrop-blur-sm">
          <span className="flex items-center gap-1 rounded-md border border-emerald-400/60 bg-emerald-950/80 px-2 py-0.5 text-[10px] font-black tracking-wider text-emerald-300 shadow-md">
            <CheckCircle className="h-3 w-3 text-emerald-400" aria-hidden="true" />
            <span>x1</span>
          </span>
        </div>
      </div>

      {/* Metadatos y atributos */}
      <div className="mt-2.5 flex flex-1 flex-col justify-between gap-1.5">
        <div>
          <div className="flex items-center justify-between gap-1 text-[10px]">
            <span className="truncate font-mono text-slate-400" title={card.code}>
              {card.code}
            </span>
            <span className="shrink-0 rounded border border-slate-600/60 bg-slate-800/60 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-300">
              Común
            </span>
          </div>
          <h4
            className="mt-0.5 truncate text-xs font-bold text-slate-100 transition-colors group-hover:text-amber-200"
            title={card.name}
          >
            {card.name}
          </h4>
          <div className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-indigo-300/90">
            <Flame className="h-3 w-3 shrink-0 text-indigo-400" aria-hidden="true" />
            <span className="truncate font-medium" title={card.ability_name}>
              {card.ability_name || card.ability_code}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-white/10 pt-1.5 text-[11px]">
          <span className="flex items-center gap-1 font-semibold text-red-400">
            <Zap className="h-3 w-3 fill-red-400/20" aria-hidden="true" />
            <span>{card.power} PWR</span>
          </span>
          <span className="text-[10px] text-slate-400">Colección Inicial</span>
        </div>
      </div>
    </article>
  );
}
