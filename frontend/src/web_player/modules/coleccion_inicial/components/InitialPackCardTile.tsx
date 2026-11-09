/**
 * Componente visual para representar una carta común del paquete inicial (US 3.1.1).
 *
 * Responsabilidades:
 * 1. Presentar el nombre, código canónico (`PKA-<TIPO>-<NNN>`) y la rareza común.
 * 2. Inferir la identidad visual elemental (colores, gradientes, ícono y etiqueta)
 *    a partir del código canónico (`FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC`).
 * 3. Aplicar un estilo neutro seguro si el código no coincide con el patrón esperado.
 * 4. Representar estéticamente la carta sin inventar atributos de juego ni realizar
 *    llamadas HTTP para imágenes mientras no exista un endpoint de miniaturas de GridFS.
 */

import React from "react";
import {
  Droplets,
  Flame,
  Leaf,
  Shield,
  Sparkles,
  Swords,
  Zap,
} from "lucide-react";
import type { InitialPackCardDTO } from "../types/initial_pack.types";

export interface InitialPackCardTileProps {
  readonly card: InitialPackCardDTO;
  readonly className?: string;
}

interface ElementTheme {
  readonly label: string;
  readonly typeCode: string;
  readonly cardBorder: string;
  readonly cardGradient: string;
  readonly badgeBg: string;
  readonly badgeText: string;
  readonly iconColor: string;
  readonly emblemBg: string;
  readonly IconComponent: React.ComponentType<{ className?: string }>;
}

const ELEMENT_THEMES: Record<string, ElementTheme> = Object.freeze({
  FUE: Object.freeze({
    label: "Fuego",
    typeCode: "FUE",
    cardBorder: "border-orange-500/50 hover:border-orange-400",
    cardGradient: "from-orange-950/40 via-red-950/30 to-slate-900",
    badgeBg: "bg-orange-500/20 border-orange-500/40",
    badgeText: "text-orange-300",
    iconColor: "text-orange-400",
    emblemBg: "bg-gradient-to-tr from-orange-600/30 to-red-600/20 border-orange-500/30",
    IconComponent: Flame,
  }),
  AGU: Object.freeze({
    label: "Agua",
    typeCode: "AGU",
    cardBorder: "border-blue-500/50 hover:border-blue-400",
    cardGradient: "from-blue-950/40 via-cyan-950/30 to-slate-900",
    badgeBg: "bg-blue-500/20 border-blue-500/40",
    badgeText: "text-blue-300",
    iconColor: "text-blue-400",
    emblemBg: "bg-gradient-to-tr from-blue-600/30 to-cyan-600/20 border-blue-500/30",
    IconComponent: Droplets,
  }),
  PLA: Object.freeze({
    label: "Planta",
    typeCode: "PLA",
    cardBorder: "border-emerald-500/50 hover:border-emerald-400",
    cardGradient: "from-emerald-950/40 via-green-950/30 to-slate-900",
    badgeBg: "bg-emerald-500/20 border-emerald-500/40",
    badgeText: "text-emerald-300",
    iconColor: "text-emerald-400",
    emblemBg: "bg-gradient-to-tr from-emerald-600/30 to-green-600/20 border-emerald-500/30",
    IconComponent: Leaf,
  }),
  ELE: Object.freeze({
    label: "Eléctrico",
    typeCode: "ELE",
    cardBorder: "border-amber-500/50 hover:border-amber-400",
    cardGradient: "from-amber-950/40 via-yellow-950/30 to-slate-900",
    badgeBg: "bg-amber-500/20 border-amber-500/40",
    badgeText: "text-amber-300",
    iconColor: "text-amber-400",
    emblemBg: "bg-gradient-to-tr from-amber-600/30 to-yellow-600/20 border-amber-500/30",
    IconComponent: Zap,
  }),
  PSI: Object.freeze({
    label: "Psíquico",
    typeCode: "PSI",
    cardBorder: "border-purple-500/50 hover:border-purple-400",
    cardGradient: "from-purple-950/40 via-fuchsia-950/30 to-slate-900",
    badgeBg: "bg-purple-500/20 border-purple-500/40",
    badgeText: "text-purple-300",
    iconColor: "text-purple-400",
    emblemBg: "bg-gradient-to-tr from-purple-600/30 to-fuchsia-600/20 border-purple-500/30",
    IconComponent: Sparkles,
  }),
  LUC: Object.freeze({
    label: "Lucha",
    typeCode: "LUC",
    cardBorder: "border-amber-700/50 hover:border-amber-600",
    cardGradient: "from-stone-900 via-amber-950/30 to-slate-900",
    badgeBg: "bg-amber-700/20 border-amber-600/40",
    badgeText: "text-amber-300",
    iconColor: "text-amber-400",
    emblemBg: "bg-gradient-to-tr from-stone-700/30 to-amber-800/20 border-amber-600/30",
    IconComponent: Swords,
  }),
});

const NEUTRAL_THEME: ElementTheme = Object.freeze({
  label: "Básica",
  typeCode: "STD",
  cardBorder: "border-slate-700 hover:border-slate-500",
  cardGradient: "from-slate-900 via-slate-800/40 to-slate-900",
  badgeBg: "bg-slate-700/30 border-slate-600/40",
  badgeText: "text-slate-300",
  iconColor: "text-slate-400",
  emblemBg: "bg-gradient-to-tr from-slate-700/30 to-slate-800/30 border-slate-600/30",
  IconComponent: Shield,
});

const CODE_ELEMENT_PATTERN = /^PKA-(FUE|AGU|PLA|ELE|PSI|LUC)-[0-9]{3}$/;

/**
 * Infiere el tema elemental a partir del código de la carta (`PKA-<TIPO>-<NNN>`).
 */
export function resolveElementTheme(code: string): ElementTheme {
  const match = CODE_ELEMENT_PATTERN.exec(code.trim().toUpperCase());
  if (!match || !match[1]) {
    return NEUTRAL_THEME;
  }
  return ELEMENT_THEMES[match[1]] ?? NEUTRAL_THEME;
}

export function InitialPackCardTile({
  card,
  className = "",
}: InitialPackCardTileProps): React.ReactElement {
  const theme = resolveElementTheme(card.code);
  const { IconComponent } = theme;

  return (
    <article
      tabIndex={0}
      aria-label={`${card.name} (${card.code}) - Carta Común de tipo ${theme.label}`}
      className={`group relative flex flex-col justify-between overflow-hidden rounded-2xl border bg-gradient-to-b ${theme.cardGradient} ${theme.cardBorder} p-3.5 shadow-lg transition-all duration-200 hover:-translate-y-1 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 aspect-[5/7] ${className}`}
    >
      {/* Encabezado: Código y Rareza */}
      <div className="flex items-center justify-between gap-1 text-[10px]">
        <span
          className="font-mono font-semibold text-slate-300 tracking-wider truncate max-w-[90px]"
          title={card.code}
        >
          {card.code}
        </span>
        <span className="shrink-0 rounded-full border border-slate-700/80 bg-slate-900/80 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-300 shadow-sm">
          Común
        </span>
      </div>

      {/* Área central estilizada: Emblema elemental */}
      <div className="my-auto flex flex-col items-center justify-center py-2">
        <div
          className={`relative flex h-16 w-16 items-center justify-center rounded-2xl border shadow-inner ${theme.emblemBg} transition-transform duration-200 group-hover:scale-110`}
        >
          <IconComponent className={`h-8 w-8 ${theme.iconColor}`} aria-hidden="true" />
          <div className="absolute -bottom-2 shrink-0">
            <span
              className={`rounded-md border px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider shadow ${theme.badgeBg} ${theme.badgeText}`}
            >
              {theme.label}
            </span>
          </div>
        </div>
      </div>

      {/* Pie: Nombre de la carta y pie de colección inicial */}
      <div className="border-t border-slate-800/80 pt-2">
        <h4
          className="truncate text-xs font-bold text-white transition-colors group-hover:text-amber-200"
          title={card.name}
        >
          {card.name}
        </h4>
        <div className="mt-0.5 flex items-center justify-between text-[10px] text-slate-400">
          <span>Colección Inicial</span>
          <span className="font-mono text-[9px] text-slate-500">1x</span>
        </div>
      </div>
    </article>
  );
}
