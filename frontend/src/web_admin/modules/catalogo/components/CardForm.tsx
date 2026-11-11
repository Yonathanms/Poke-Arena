/**
 * Formulario de Crear Carta para administradores (US 2.1.1).
 */

import React, { useId } from "react";
import { Loader2, RefreshCw, RotateCcw, Save } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import type {
  AbilityOptionDTO,
  CardFieldErrors,
  CardRarity,
  CardType,
  CreateCardFormValues,
  ValidatedCardImageSelection,
} from "../types/card-admin.types";
import {
  CARD_RARITIES,
  CARD_TYPES,
  CARD_VALIDATION_CONSTRAINTS,
  normalizeCardName,
} from "../validation/card-validation";
import { CardImageUploader } from "./CardImageUploader";
import { CARD_RARITY_VISUAL_META, CARD_TYPE_VISUAL_META } from "./CardPreviewCard";

export interface CardFormProps {
  readonly values: CreateCardFormValues;
  readonly errors: CardFieldErrors;
  readonly imageSelection: ValidatedCardImageSelection | null;
  readonly abilities: readonly AbilityOptionDTO[];
  readonly isLoadingAbilities: boolean;
  readonly abilitiesError: string | null;
  readonly isSubmitting: boolean;
  readonly disabled?: boolean;
  readonly onChange: <K extends keyof CreateCardFormValues>(
    field: K,
    value: CreateCardFormValues[K]
  ) => void;
  readonly onImageChange: (
    selection: ValidatedCardImageSelection | null,
    validationError?: string | null
  ) => void;
  readonly onReloadAbilities: () => void;
  readonly onSubmit: () => void;
  readonly onReset: () => void;
}

export function CardForm({
  values,
  errors,
  imageSelection,
  abilities,
  isLoadingAbilities,
  abilitiesError,
  isSubmitting,
  disabled = false,
  onChange,
  onImageChange,
  onReloadAbilities,
  onSubmit,
  onReset,
}: CardFormProps): React.ReactElement {
  const formId = useId();
  const isLocked = disabled || isSubmitting;
  const trimmedNameLength = normalizeCardName(values.name).length;

  const handleFormSubmit = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    if (isLocked) return;
    onSubmit();
  };

  return (
    <form
      noValidate
      onSubmit={handleFormSubmit}
      className="space-y-6 rounded-2xl glass-card border border-arena-border p-6 sm:p-8"
    >
      <div className="border-b border-arena-border/70 pb-4">
        <h3 className="text-lg font-bold tracking-tight text-white">Datos de la Carta</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          Completa los atributos oficiales. La vista previa lateral se actualiza al instante.
        </p>
      </div>

      {/* 1. Nombre */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <label
            htmlFor={`${formId}-name`}
            className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
          >
            Nombre <span className="text-red-400">*</span>
          </label>
          <span className="font-mono text-[11px] text-slate-400">
            {trimmedNameLength}/{CARD_VALIDATION_CONSTRAINTS.NAME_MAX_LENGTH}
          </span>
        </div>

        <input
          id={`${formId}-name`}
          type="text"
          required
          disabled={isLocked}
          value={values.name}
          onChange={(e) => onChange("name", e.currentTarget.value)}
          placeholder="Ej. Charizard"
          className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:outline-none focus:ring-2 disabled:opacity-60 ${
            errors.name
              ? "border-red-500/70 focus:ring-red-400/40"
              : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
          }`}
        />
        {errors.name && <p className="text-xs font-medium text-red-300">{errors.name}</p>}
      </div>

      {/* 2. Costo y 3. Poder */}
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor={`${formId}-cost`}
              className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
            >
              Costo <span className="text-red-400">*</span>
            </label>
            <span className="font-mono text-[11px] text-slate-400">
              [{CARD_VALIDATION_CONSTRAINTS.COST_MIN}..{CARD_VALIDATION_CONSTRAINTS.COST_MAX}]
            </span>
          </div>

          <input
            id={`${formId}-cost`}
            type="number"
            step={1}
            min={CARD_VALIDATION_CONSTRAINTS.COST_MIN}
            max={CARD_VALIDATION_CONSTRAINTS.COST_MAX}
            required
            disabled={isLocked}
            value={Number.isNaN(values.cost) ? "" : values.cost}
            onChange={(e) => {
              const raw = e.currentTarget.value;
              onChange("cost", raw === "" ? Number.NaN : Number(raw));
            }}
            className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 font-mono text-sm text-white transition focus:outline-none focus:ring-2 disabled:opacity-60 ${
              errors.cost
                ? "border-red-500/70 focus:ring-red-400/40"
                : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
            }`}
          />
          {errors.cost && <p className="text-xs font-medium text-red-300">{errors.cost}</p>}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor={`${formId}-power`}
              className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
            >
              Poder <span className="text-red-400">*</span>
            </label>
            <span className="font-mono text-[11px] text-slate-400">
              [{CARD_VALIDATION_CONSTRAINTS.POWER_MIN}..{CARD_VALIDATION_CONSTRAINTS.POWER_MAX}]
            </span>
          </div>

          <input
            id={`${formId}-power`}
            type="number"
            step={1}
            min={CARD_VALIDATION_CONSTRAINTS.POWER_MIN}
            max={CARD_VALIDATION_CONSTRAINTS.POWER_MAX}
            required
            disabled={isLocked}
            value={Number.isNaN(values.power) ? "" : values.power}
            onChange={(e) => {
              const raw = e.currentTarget.value;
              onChange("power", raw === "" ? Number.NaN : Number(raw));
            }}
            className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 font-mono text-sm text-white transition focus:outline-none focus:ring-2 disabled:opacity-60 ${
              errors.power
                ? "border-red-500/70 focus:ring-red-400/40"
                : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
            }`}
          />
          {errors.power && <p className="text-xs font-medium text-red-300">{errors.power}</p>}
        </div>
      </div>

      {/* 4. Tipo y 5. Rareza */}
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label
            htmlFor={`${formId}-type`}
            className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
          >
            Tipo Elemental <span className="text-red-400">*</span>
          </label>
          <select
            id={`${formId}-type`}
            disabled={isLocked}
            value={values.card_type}
            onChange={(e) => onChange("card_type", e.currentTarget.value as CardType)}
            className="w-full rounded-xl border border-arena-border bg-arena-surface/90 px-4 py-2.5 text-sm text-white transition focus:border-arena-accent focus:outline-none focus:ring-2 focus:ring-blue-500/30 disabled:opacity-60"
          >
            {CARD_TYPES.map((typeCode) => (
              <option key={typeCode} value={typeCode}>
                {typeCode} — {CARD_TYPE_VISUAL_META[typeCode].label}
              </option>
            ))}
          </select>
          {errors.card_type && (
            <p className="text-xs font-medium text-red-300">{errors.card_type}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor={`${formId}-rarity`}
            className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
          >
            Rareza <span className="text-red-400">*</span>
          </label>
          <select
            id={`${formId}-rarity`}
            disabled={isLocked}
            value={values.rarity}
            onChange={(e) => onChange("rarity", e.currentTarget.value as CardRarity)}
            className="w-full rounded-xl border border-arena-border bg-arena-surface/90 px-4 py-2.5 text-sm text-white transition focus:border-arena-accent focus:outline-none focus:ring-2 focus:ring-blue-500/30 disabled:opacity-60"
          >
            {CARD_RARITIES.map((rarityCode) => {
              const meta = CARD_RARITY_VISUAL_META[rarityCode];
              return (
                <option key={rarityCode} value={rarityCode}>
                  {rarityCode} — {meta.label} ({meta.stars})
                </option>
              );
            })}
          </select>
          {errors.rarity && <p className="text-xs font-medium text-red-300">{errors.rarity}</p>}
        </div>
      </div>

      {/* 6. Habilidad */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <label
            htmlFor={`${formId}-ability`}
            className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
          >
            Habilidad <span className="text-red-400">*</span>
          </label>
          <button
            type="button"
            disabled={isLoadingAbilities || isLocked}
            onClick={onReloadAbilities}
            className="inline-flex items-center gap-1 rounded-lg border border-arena-border bg-arena-surface px-2 py-1 text-[11px] font-semibold text-slate-300 hover:text-white disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3 w-3 ${isLoadingAbilities ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            <span>Recargar</span>
          </button>
        </div>

        {abilitiesError && (
          <AlertBanner
            variant="error"
            title="Error al cargar habilidades"
            description={abilitiesError}
            actionLabel="Reintentar"
            onAction={onReloadAbilities}
          />
        )}

        <select
          id={`${formId}-ability`}
          disabled={isLocked || isLoadingAbilities}
          value={values.ability_code}
          onChange={(e) => onChange("ability_code", e.currentTarget.value)}
          className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 text-sm text-white transition focus:outline-none focus:ring-2 disabled:opacity-60 ${
            errors.ability_code
              ? "border-red-500/70 focus:ring-red-400/40"
              : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
          }`}
        >
          {abilities.map((ability) => (
            <option key={ability.code} value={ability.code}>
              {ability.code} — {ability.name}
            </option>
          ))}
        </select>

        {errors.ability_code && (
          <p className="text-xs font-medium text-red-300">{errors.ability_code}</p>
        )}
      </div>

      {/* 7. Imagen */}
      <CardImageUploader
        value={imageSelection}
        onChange={onImageChange}
        disabled={isLocked}
        error={errors.image ?? null}
      />

      {/* Acciones */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-arena-border/70 pt-5">
        <button
          type="button"
          disabled={isLocked}
          onClick={onReset}
          className="inline-flex items-center gap-2 rounded-xl border border-arena-border bg-arena-surface px-4 py-2.5 text-xs font-semibold text-slate-300 transition hover:text-white disabled:opacity-50"
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Limpiar formulario</span>
        </button>

        <button
          type="submit"
          disabled={isLocked}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-600/25 transition hover:from-blue-500 hover:to-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              <span>Guardando...</span>
            </>
          ) : (
            <>
              <Save className="h-4 w-4" aria-hidden="true" />
              <span>Crear Carta</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
