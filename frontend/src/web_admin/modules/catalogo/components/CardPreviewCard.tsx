/**
 * Componente de previsualización visual en tiempo real de la carta (`CardPreviewCard.tsx`).
 *
 * Responsabilidades:
 * 1. Representar visualmente una carta de Poké-Arena en proporción `5:7` utilizando
 *    la estética oscura `arena` y la paleta cromática por tipo elemental (`FUE`, `AGU`,
 *    `PLA`, `ELE`, `PSI`, `LUC`).
 * 2. Reflejar instantáneamente los cambios de `name`, `cost`, `power`, `card_type`,
 *    `rarity`, `ability_code` (con su nombre resuelto) y la imagen validada.
 * 3. Reutilizar `imageSelection.previewUrl` generado por `CardImageUploader` (F3)
 *    sin crear ni revocar `ObjectURL`s adicionales.
 * 4. Mostrar el marcador provisional `PKA-<TIPO>-???` mientras la carta está en edición
 *    (nunca predecir el consecutivo en el cliente) y sustituirlo por el código oficial
 *    asignado por PostgreSQL (`createdCard.code`, p. ej. `PKA-LUC-001`) tras `201 Created`.
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
import type { CreateCardStatus } from "../hooks/useCreateCard";
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
  readonly status: CreateCardStatus;
  readonly createdCard: CardCreatedResponseDTO | null;
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

/**
 * Mapa estático de estilos Tailwind por tipo elemental (`FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC`).
 * Se declaran cadenas completas para que el compilador JIT de Tailwind CSS las incluya en el bundle.
 */
export const CARD_TYPE_VISUAL_META: Readonly<Record<CardType, CardTypeVisualMeta>> = Object.freeze({
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
});

export interface CardRarityVisualMeta {
  readonly code: CardRarity;
  readonly label: string;
  readonly badgeClass: string;
  readonly stars: string;
}

export const CARD_RARITY_VISUAL_META: Readonly<Record<CardRarity, CardRarityVisualMeta>> =
  Object.freeze({
    COMUN: {
      code: "COMUN",
      label: "Común",
      badgeClass: "border-slate-500/40 bg-slate-500/15 text-slate-200",
      stars: "●",
    },
    POCO_COMUN: {
      code: "POCO_COMUN",
      label: "Poco Común",
      badgeClass: "border-emerald-500/40 bg-emerald-500/15 text-emerald-200",
      stars: "◆",
    },
    RARA: {
      code: "RARA",
      label: "Rara",
      badgeClass: "border-blue-400/50 bg-blue-500/20 text-blue-200",
      stars: "★",
    },
    LEGENDARIA: {
      code: "LEGENDARIA",
      label: "Legendaria",
      badgeClass: "border-amber-400/60 bg-amber-500/20 text-amber-200",
      stars: "✦✦",
    },
  });

/**
 * Construye el marcador provisional de código público antes de que el servidor
 * asigne el consecutivo atómico en PostgreSQL (`catalog_card_code_counters`).
 */
export function formatProvisionalCardCode(cardType: CardType): string {
  return `PKA-${cardType}-???`;
}

/**
 * Formatea el valor de poder base para la ficha visual.
 */
export function formatDisplayPower(power: number): string {
  if (validateCardPower(power) !== null) {
    return "?";
  }
  if (power > 0) {
    return `+${power}`;
  }
  return String(power);
}

/**
 * Formatea el valor de costo de energía para la ficha visual.
 */
export function formatDisplayCost(cost: number): string {
  if (validateCardCost(cost) !== null) {
    return "?";
  }
  return String(cost);
}

export function CardPreviewCard({
  values,
  abilities,
  imageSelection,
  status,
  createdCard,
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
  const displayAbilityCode = values.ability_code.trim() || "HAB-???";
  const displayAbilityName = selectedAbility
    ? selectedAbility.name
    : values.ability_code.trim()
      ? "Habilidad pendiente de verificar"
      : "Selecciona una habilidad";

  const isConfirmed = status === "success" && createdCard !== null;
  const displayedPublicCode = isConfirmed
    ? createdCard.code
    : formatProvisionalCardCode(values.card_type);

  return (
    <section
      aria-label="Previsualización de la carta en tiempo real"
      className="space-y-4"
    >
      {/* Encabezado del panel de vista previa */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Vista Previa en Tiempo Real
          </h3>
          <p className="text-xs text-slate-400">
            Proporción oficial 5:7 · Paleta elemental {typeMeta.label} ({typeMeta.code})
          </p>
        </div>

        {isConfirmed ? (
          <span
            data-testid="preview-status-badge"
            className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-300"
          >
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            Confirmada · {createdCard.image_status}
          </span>
        ) : status === "submitting" ? (
          <span
            data-testid="preview-status-badge"
            className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/40 bg-blue-500/15 px-3 py-1 text-xs font-semibold text-blue-200"
          >
            <Clock className="h-3.5 w-3.5 animate-pulse" aria-hidden="true" />
            Enviando al servidor...
          </span>
        ) : status === "uncertain_outcome" ? (
          <span
            data-testid="preview-status-badge"
            className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-200"
          >
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            Confirmación pendiente
          </span>
        ) : (
          <span
            data-testid="preview-status-badge"
            className="inline-flex items-center gap-1.5 rounded-full border border-arena-border bg-arena-surface px-3 py-1 text-xs font-semibold text-slate-300"
          >
            Borrador en edición
          </span>
        )}
      </div>

      {/* Marco físico de la carta en proporción 5:7 */}
      <div className="mx-auto w-full max-w-[340px]">
        <article
          aria-label={`Carta ${displayName} (${displayedPublicCode})`}
          className={`aspect-[5/7] w-full rounded-3xl border-2 ${typeMeta.frameBorderClass} bg-gradient-to-b ${typeMeta.headerBgClass} p-3.5 shadow-2xl ${typeMeta.glowClass} flex flex-col justify-between transition-colors`}
        >
          {/* Barra superior: Costo, Nombre y Tipo Elemental */}
          <header className="flex items-center justify-between gap-2 rounded-2xl border border-white/10 bg-arena-bg/75 px-3 py-2 backdrop-blur-sm">
            <div className="flex items-center gap-2.5 min-w-0">
              <div
                title={`Costo de energía: ${displayCost}`}
                aria-label={`Costo de energía: ${displayCost}`}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-blue-400/50 bg-gradient-to-br from-blue-600 to-indigo-700 font-mono text-sm font-extrabold text-white shadow-md"
              >
                {displayCost}
              </div>

              <div className="min-w-0">
                <h4
                  data-testid="preview-card-name"
                  className={`truncate text-sm font-extrabold tracking-tight ${
                    isNamePlaceholder ? "italic text-slate-400" : "text-white"
                  }`}
                  title={displayName}
                >
                  {displayName}
                </h4>
                <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  {rarityMeta.stars} {rarityMeta.label}
                </p>
              </div>
            </div>

            <span
              data-testid="preview-card-type"
              className={`inline-flex shrink-0 items-center gap-1 rounded-xl border px-2 py-1 text-[11px] font-bold uppercase tracking-wider ${typeMeta.badgeClass}`}
            >
              <TypeIcon className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{typeMeta.code}</span>
            </span>
          </header>

          {/* Ventana de ilustración (reutiliza previewUrl de CardImageUploader sin crear otro ObjectURL) */}
          <div className="my-2.5 relative flex-1 overflow-hidden rounded-2xl border border-white/15 bg-arena-bg/90 shadow-inner">
            {imageSelection ? (
              <img
                data-testid="preview-card-image"
                src={imageSelection.previewUrl}
                alt={`Ilustración de ${displayName}`}
                className="h-full w-full object-cover"
              />
            ) : (
              <div
                data-testid="preview-card-image-placeholder"
                className="flex h-full w-full flex-col items-center justify-center p-4 text-center"
              >
                <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-2xl border border-arena-border bg-arena-surface/80 text-slate-400">
                  <ImageIcon className="h-6 w-6" aria-hidden="true" />
                </div>
                <p className="text-xs font-semibold text-slate-300">
                  Sin ilustración seleccionada
                </p>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  Proporción 5:7 · Mín. 600 × 840 px
                </p>
              </div>
            )}

            {/* Etiqueta flotante de rareza sobre la esquina inferior de la ilustración */}
            <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between gap-2 pointer-events-none">
              <span
                data-testid="preview-card-rarity"
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

          {/* Caja de habilidad y estadísticas inferiores */}
          <footer className="space-y-2">
            <div className="rounded-xl border border-white/10 bg-arena-bg/80 px-3 py-2 backdrop-blur-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Habilidad
                </span>
                <span
                  data-testid="preview-ability-code"
                  className="rounded border border-arena-border bg-arena-surface px-1.5 py-0.5 font-mono text-[10px] font-semibold text-blue-300"
                >
                  {displayAbilityCode}
                </span>
              </div>
              <p
                data-testid="preview-ability-name"
                className="mt-0.5 truncate text-xs font-bold text-slate-100"
                title={displayAbilityName}
              >
                {displayAbilityName}
              </p>
            </div>

            {/* Pie de carta: Código público (provisional o confirmado) y Poder */}
            <div className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-arena-bg/90 px-3 py-1.5">
              <div className="min-w-0">
                <span className="block text-[9px] uppercase tracking-wider text-slate-400">
                  {isConfirmed ? "Código Oficial Asignado" : "Código Provisional"}
                </span>
                <span
                  data-testid="preview-card-code"
                  className={`font-mono text-xs font-bold ${
                    isConfirmed ? "text-emerald-300" : "text-slate-300"
                  }`}
                >
                  {displayedPublicCode}
                </span>
              </div>

              <div
                title={`Poder base: ${displayPower}`}
                aria-label={`Poder base: ${displayPower}`}
                className="flex items-center gap-1.5 rounded-lg border border-arena-border bg-arena-surface px-2.5 py-1"
              >
                <Shield className={`h-3.5 w-3.5 ${typeMeta.accentTextClass}`} aria-hidden="true" />
                <span className="text-[10px] font-semibold uppercase text-slate-400">Poder</span>
                <span
                  data-testid="preview-card-power"
                  className="font-mono text-xs font-extrabold text-white"
                >
                  {displayPower}
                </span>
              </div>
            </div>
          </footer>
        </article>
      </div>

      {/* Nota explicativa sobre el código y metadatos confirmados tras 201 Created */}
      {isConfirmed ? (
        <div
          data-testid="preview-confirmed-metadata"
          className="rounded-2xl border border-emerald-500/30 bg-emerald-950/25 p-3.5 text-xs text-slate-200 space-y-1.5"
        >
          <p className="font-semibold text-emerald-300">
            Registro persistido en PostgreSQL y GridFS
          </p>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-[11px]">
            <div>
              <dt className="text-slate-400">Código:</dt>
              <dd className="font-bold text-white">{createdCard.code}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Estado imagen:</dt>
              <dd className="font-bold text-emerald-300">{createdCard.image_status}</dd>
            </div>
            <div className="col-span-2 truncate" title={createdCard.id}>
              <dt className="inline text-slate-400">ID Carta: </dt>
              <dd className="inline text-slate-200">{createdCard.id}</dd>
            </div>
            <div className="col-span-2 truncate" title={createdCard.image_id}>
              <dt className="inline text-slate-400">ID Imagen: </dt>
              <dd className="inline text-slate-200">{createdCard.image_id}</dd>
            </div>
          </dl>
        </div>
      ) : (
        <p className="text-center text-[11px] text-slate-400">
          El código consecutivo definitivo (<code className="font-mono text-slate-300">PKA-{values.card_type}-NNN</code>) será asignado atómicamente por el backend al confirmar la creación.
        </p>
      )}
    </section>
  );
}
