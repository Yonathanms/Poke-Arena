/**
 * Panel de previsualización en tiempo real de la carta (`CardPreviewCard.tsx`).
 * Muestra los cambios del formulario en proporción 5:7 y el código provisional
 * `PKA-[TIPO]-???` hasta que el backend asigne el código oficial.
 */

import React from "react";
import {
  CheckCircle2,
  Clock,
  Droplets,
  Flame,
  Image as ImageIcon,
  Leaf,
  Shield,
  Sparkles,
  Swords,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type {
  AbilityOptionDTO,
  CardCreatedResponseDTO,
  CardRarity,
  CardType,
  CreateCardFormValues,
  ValidatedCardImageSelection,
} from "../types/card-admin.types";
import {
  normalizeCardName,
  validateCardCost,
  validateCardPower,
} from "../validation/card-validation";

export interface CardPreviewCardProps {
  readonly values: CreateCardFormValues;
  readonly abilities: readonly AbilityOptionDTO[];
  readonly imageSelection: ValidatedCardImageSelection | null;
  readonly isSubmitting?: boolean;
  readonly createdCard?: CardCreatedResponseDTO | null;
}

export interface CardTypeVisualMeta {
  readonly code: CardType;
  readonly label: string;
  readonly frameBorderClass: string;
  readonly headerBgClass: string;
  readonly badgeClass: string;
  readonly accentTextClass: string;
  readonly glowClass: string;
  readonly Icon: LucideIcon;
}

export const CARD_TYPE_VISUAL_META: Readonly<Record<string, CardTypeVisualMeta>> = {
  FUE: {
    code: "FUE",
    label: "Fuego",
    frameBorderClass: "border-type-FUE/70",
    headerBgClass: "from-red-950/90 via-arena-card to-arena-surface",
    badgeClass: "border-type-FUE/50 bg-type-FUE/20 text-red-200",
    accentTextClass: "text-type-FUE",
    glowClass: "shadow-red-500/15",
    Icon: Flame,
  },
  AGU: {
    code: "AGU",
    label: "Agua",
    frameBorderClass: "border-type-AGU/70",
    headerBgClass: "from-blue-950/90 via-arena-card to-arena-surface",
    badgeClass: "border-type-AGU/50 bg-type-AGU/20 text-blue-200",
    accentTextClass: "text-type-AGU",
    glowClass: "shadow-blue-500/15",
    Icon: Droplets,
  },
  PLA: {
    code: "PLA",
    label: "Planta",
    frameBorderClass: "border-type-PLA/70",
    headerBgClass: "from-emerald-950/90 via-arena-card to-arena-surface",
    badgeClass: "border-type-PLA/50 bg-type-PLA/20 text-emerald-200",
    accentTextClass: "text-type-PLA",
    glowClass: "shadow-emerald-500/15",
    Icon: Leaf,
  },
  ELE: {
    code: "ELE",
    label: "Eléctrico",
    frameBorderClass: "border-type-ELE/70",
    headerBgClass: "from-amber-950/90 via-arena-card to-arena-surface",
    badgeClass: "border-type-ELE/50 bg-type-ELE/20 text-amber-200",
    accentTextClass: "text-type-ELE",
    glowClass: "shadow-amber-500/15",
    Icon: Zap,
  },
  PSI: {
    code: "PSI",
    label: "Psíquico",
    frameBorderClass: "border-type-PSI/70",
    headerBgClass: "from-purple-950/90 via-arena-card to-arena-surface",
    badgeClass: "border-type-PSI/50 bg-type-PSI/20 text-purple-200",
    accentTextClass: "text-type-PSI",
    glowClass: "shadow-purple-500/15",
    Icon: Sparkles,
  },
  LUC: {
    code: "LUC",
    label: "Lucha",
    frameBorderClass: "border-type-LUC/70",
    headerBgClass: "from-orange-950/90 via-arena-card to-arena-surface",
    badgeClass: "border-type-LUC/50 bg-type-LUC/20 text-orange-200",
    accentTextClass: "text-type-LUC",
    glowClass: "shadow-orange-500/15",
    Icon: Swords,
  },
};

export interface CardRarityVisualMeta {
  readonly code: CardRarity;
  readonly label: string;
  readonly badgeClass: string;
}

export const CARD_RARITY_VISUAL_META: Readonly<Record<string, CardRarityVisualMeta>> = {
  COMUN: {
    code: "COMUN",
    label: "Común",
    badgeClass: "border-slate-500/40 bg-slate-500/15 text-slate-200",
  },
  POCO_COMUN: {
    code: "POCO_COMUN",
    label: "Poco Común",
    badgeClass: "border-emerald-500/40 bg-emerald-500/15 text-emerald-200",
  },
  RARA: {
    code: "RARA",
    label: "Rara",
    badgeClass: "border-blue-400/50 bg-blue-500/20 text-blue-200",
  },
  LEGENDARIA: {
    code: "LEGENDARIA",
    label: "Legendaria",
    badgeClass: "border-amber-400/60 bg-amber-500/20 text-amber-200",
  },
};

export function formatProvisionalCardCode(cardType: CardType): string {
  return `PKA-${cardType}-???`;
}

export function formatDisplayPower(power: number): string {
  if (validateCardPower(power) !== null) return "?";
  return power > 0 ? `+${power}` : String(power);
}

export function formatDisplayCost(cost: number): string {
  if (validateCardCost(cost) !== null) return "?";
  return String(cost);
}

export function CardPreviewCard({
  values,
  abilities,
  imageSelection,
  isSubmitting = false,
  createdCard = null,
}: CardPreviewCardProps): React.ReactElement {
  const typeMeta = CARD_TYPE_VISUAL_META[values.card_type] ?? CARD_TYPE_VISUAL_META.FUE;
  const rarityMeta = CARD_RARITY_VISUAL_META[values.rarity] ?? CARD_RARITY_VISUAL_META.COMUN;
  const { Icon: TypeIcon } = typeMeta;

  const trimmedName = normalizeCardName(values.name);
  const displayName = trimmedName.length > 0 ? trimmedName : "Nombre de la carta";
  const isNamePlaceholder = trimmedName.length === 0;

  const displayCost = formatDisplayCost(values.cost);
  const displayPower = formatDisplayPower(values.power);

  const selectedAbility = abilities.find((item) => item.code === values.ability_code.trim());
  const displayAbilityCode = values.ability_code.trim() || "HAB-000";
  const displayAbilityName = selectedAbility ? selectedAbility.name : "Sin Habilidad";

  const isConfirmed = createdCard !== null;
  const displayedPublicCode = isConfirmed
    ? createdCard.code
    : formatProvisionalCardCode(values.card_type);

  return (
    <section aria-label="Previsualización de la carta en tiempo real" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Vista Previa
          </h3>
          <p className="text-xs text-slate-400">
            Proporción 5:7 · {typeMeta.label} ({typeMeta.code})
          </p>
        </div>

        {isConfirmed ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            {createdCard.image_status}
          </span>
        ) : isSubmitting ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/40 bg-blue-500/15 px-3 py-1 text-xs font-semibold text-blue-200">
            <Clock className="h-3.5 w-3.5 animate-pulse" aria-hidden="true" />
            Guardando...
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-arena-border bg-arena-surface px-3 py-1 text-xs font-semibold text-slate-300">
            En edición
          </span>
        )}
      </div>

      <div className="mx-auto w-full max-w-[340px]">
        <article
          aria-label={`Carta ${displayName} (${displayedPublicCode})`}
          className={`aspect-[5/7] w-full rounded-3xl border-2 ${typeMeta.frameBorderClass} bg-gradient-to-b ${typeMeta.headerBgClass} p-3.5 shadow-2xl ${typeMeta.glowClass} flex flex-col justify-between transition-colors`}
        >
          <header className="flex items-center justify-between gap-2 rounded-2xl border border-white/10 bg-arena-bg/75 px-3 py-2 backdrop-blur-sm">
            <div className="flex items-center gap-2.5 min-w-0">
              <div
                title={`Costo: ${displayCost}`}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-blue-400/50 bg-gradient-to-br from-blue-600 to-indigo-700 font-mono text-sm font-extrabold text-white shadow-md"
              >
                {displayCost}
              </div>

              <div className="min-w-0">
                <h4
                  className={`truncate text-sm font-extrabold tracking-tight ${
                    isNamePlaceholder ? "italic text-slate-400" : "text-white"
                  }`}
                  title={displayName}
                >
                  {displayName}
                </h4>
                <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  {rarityMeta.label}
                </p>
              </div>
            </div>

            <span
              className={`inline-flex shrink-0 items-center gap-1 rounded-xl border px-2 py-1 text-[11px] font-bold uppercase tracking-wider ${typeMeta.badgeClass}`}
            >
              <TypeIcon className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{typeMeta.code}</span>
            </span>
          </header>

          <div className="my-2.5 relative flex-1 overflow-hidden rounded-2xl border border-white/15 bg-arena-bg/90 shadow-inner">
            {imageSelection ? (
              <img
                src={imageSelection.previewUrl}
                alt={`Ilustración de ${displayName}`}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center p-4 text-center">
                <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-2xl border border-arena-border bg-arena-surface/80 text-slate-400">
                  <ImageIcon className="h-6 w-6" aria-hidden="true" />
                </div>
                <p className="text-xs font-semibold text-slate-300">Sin ilustración</p>
                <p className="mt-0.5 text-[11px] text-slate-500">5:7 · Mín. 600 × 840 px</p>
              </div>
            )}

            <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between gap-2 pointer-events-none">
              <span
                className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider backdrop-blur-md ${rarityMeta.badgeClass}`}
              >
                {rarityMeta.code}
              </span>

              {imageSelection && (
                <span className="rounded-lg border border-white/15 bg-arena-bg/80 px-2 py-0.5 font-mono text-[10px] text-slate-300 backdrop-blur-md">
                  {imageSelection.dimensions.width}×{imageSelection.dimensions.height}
                </span>
              )}
            </div>
          </div>

          <footer className="space-y-2">
            <div className="rounded-xl border border-white/10 bg-arena-bg/80 px-3 py-2 backdrop-blur-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Habilidad
                </span>
                <span className="rounded border border-arena-border bg-arena-surface px-1.5 py-0.5 font-mono text-[10px] font-semibold text-blue-300">
                  {displayAbilityCode}
                </span>
              </div>
              <p className="mt-0.5 truncate text-xs font-bold text-slate-100" title={displayAbilityName}>
                {displayAbilityName}
              </p>
            </div>

            <div className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-arena-bg/90 px-3 py-1.5">
              <div className="min-w-0">
                <span className="block text-[9px] uppercase tracking-wider text-slate-400">
                  {isConfirmed ? "Código Oficial" : "Código Provisional"}
                </span>
                <span
                  className={`font-mono text-xs font-bold ${
                    isConfirmed ? "text-emerald-300" : "text-slate-300"
                  }`}
                >
                  {displayedPublicCode}
                </span>
              </div>

              <div
                title={`Poder: ${displayPower}`}
                className="flex items-center gap-1.5 rounded-lg border border-arena-border bg-arena-surface px-2.5 py-1"
              >
                <Shield className={`h-3.5 w-3.5 ${typeMeta.accentTextClass}`} aria-hidden="true" />
                <span className="text-[10px] font-semibold uppercase text-slate-400">Poder</span>
                <span className="font-mono text-xs font-extrabold text-white">{displayPower}</span>
              </div>
            </div>
          </footer>
        </article>
      </div>
    </section>
  );
}
