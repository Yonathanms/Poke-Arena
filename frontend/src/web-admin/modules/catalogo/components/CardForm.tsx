/**
 * Formulario controlado y accesible para 2.1.1 — Crear Carta (`CardForm.tsx`).
 *
 * Responsabilidades:
 * 1. Presentar controles etiquetados (`<label htmlFor>`, `aria-invalid`, `aria-describedby`)
 *    para `name`, `cost`, `power`, `card_type`, `rarity`, `ability_code` e `image`.
 * 2. Integrar el selector de habilidades alimentado por `useAbilities` (soportando carga,
 *    error con reintento manual, lista vacía e invalidación de habilidad tras recarga).
 * 3. Integrar `CardImageUploader` (F3) sin duplicar su lógica de validación o `ObjectURL`.
 * 4. Impedir el recorte silencioso de números inválidos y exponer mensajes de error claros
 *    por campo utilizando las reglas de `card-validation.ts`.
 * 5. Bloquear la edición durante `submitting`, `uncertain_outcome` o `success`, ofreciendo
 *    las acciones explícitas de replay seguro o reinicio según el estado de la máquina.
 */

import React, { useId } from "react";
import {
  Loader2,
  Lock,
  PlusCircle,
  RefreshCw,
  RotateCcw,
  Save,
  Sparkles,
  Unlock,
} from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import type { AbilitiesErrorInfo } from "../hooks/useAbilities";
import type { CreateCardStatus } from "../hooks/useCreateCard";
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
  type ImageDimensionsDecoder,
  type ObjectUrlManager,
} from "../validation/card-validation";
import { CardImageUploader } from "./CardImageUploader";
import { CARD_RARITY_VISUAL_META, CARD_TYPE_VISUAL_META } from "./CardPreviewCard";

export interface CardFormProps {
  readonly values: CreateCardFormValues;
  readonly rawCostInput: string;
  readonly rawPowerInput: string;
  readonly imageSelection: ValidatedCardImageSelection | null;
  readonly fieldErrors: CardFieldErrors;
  readonly status: CreateCardStatus;
  readonly isSubmitting: boolean;
  readonly isEditingLocked: boolean;
  readonly activeIdempotencyKey: string | null;
  readonly abilities: readonly AbilityOptionDTO[];
  readonly isLoadingAbilities: boolean;
  readonly hasLoadedAbilities: boolean;
  readonly isAbilitiesEmpty: boolean;
  readonly abilitiesError: AbilitiesErrorInfo | null;
  readonly onNameChange: (name: string) => void;
  readonly onCostInputChange: (rawCost: string) => void;
  readonly onPowerInputChange: (rawPower: string) => void;
  readonly onCardTypeChange: (cardType: CardType) => void;
  readonly onRarityChange: (rarity: CardRarity) => void;
  readonly onAbilityCodeChange: (abilityCode: string) => void;
  readonly onImageChange: (selection: ValidatedCardImageSelection | null) => void;
  readonly onImageValidationErrorChange: (errorMessage: string | null) => void;
  readonly onReloadAbilities: () => Promise<unknown> | void;
  readonly onSubmit: () => Promise<unknown> | void;
  readonly onRetryPendingOperation: () => Promise<unknown> | void;
  readonly onAbandonUncertainOperation: () => void;
  readonly onStartNewCard: () => void;
  readonly customUrlManager?: ObjectUrlManager;
  readonly customDimensionsDecoder?: ImageDimensionsDecoder;
}

export function CardForm({
  values,
  rawCostInput,
  rawPowerInput,
  imageSelection,
  fieldErrors,
  status,
  isSubmitting,
  isEditingLocked,
  activeIdempotencyKey,
  abilities,
  isLoadingAbilities,
  hasLoadedAbilities,
  isAbilitiesEmpty,
  abilitiesError,
  onNameChange,
  onCostInputChange,
  onPowerInputChange,
  onCardTypeChange,
  onRarityChange,
  onAbilityCodeChange,
  onImageChange,
  onImageValidationErrorChange,
  onReloadAbilities,
  onSubmit,
  onRetryPendingOperation,
  onAbandonUncertainOperation,
  onStartNewCard,
  customUrlManager,
  customDimensionsDecoder,
}: CardFormProps): React.ReactElement {
  const formId = useId();
  const nameInputId = `${formId}-name`;
  const nameHintId = `${formId}-name-hint`;
  const nameErrorId = `${formId}-name-error`;

  const costInputId = `${formId}-cost`;
  const costHintId = `${formId}-cost-hint`;
  const costErrorId = `${formId}-cost-error`;

  const powerInputId = `${formId}-power`;
  const powerHintId = `${formId}-power-hint`;
  const powerErrorId = `${formId}-power-error`;

  const typeSelectId = `${formId}-card-type`;
  const typeHintId = `${formId}-card-type-hint`;
  const typeErrorId = `${formId}-card-type-error`;

  const raritySelectId = `${formId}-rarity`;
  const rarityHintId = `${formId}-rarity-hint`;
  const rarityErrorId = `${formId}-rarity-error`;

  const abilitySelectId = `${formId}-ability-code`;
  const abilityHintId = `${formId}-ability-code-hint`;
  const abilityErrorId = `${formId}-ability-code-error`;

  const trimmedNameLength = normalizeCardName(values.name).length;
  const isCurrentAbilityInCatalog = abilities.some(
    (item) => item.code === values.ability_code.trim()
  );

  const isSubmitDisabled =
    isSubmitting ||
    isEditingLocked ||
    isLoadingAbilities ||
    abilitiesError !== null ||
    (hasLoadedAbilities && isAbilitiesEmpty);

  const handleFormSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (status === "uncertain_outcome") {
      void onRetryPendingOperation();
      return;
    }
    if (isSubmitDisabled) {
      return;
    }
    void onSubmit();
  };

  return (
    <form
      noValidate
      onSubmit={handleFormSubmit}
      aria-label="Formulario administrativo para Crear Carta"
      className="space-y-6 rounded-2xl glass-card border border-arena-border p-6 sm:p-8"
    >
      {/* Cabecera del formulario */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-arena-border/70 pb-4">
        <div>
          <h3 className="text-lg font-bold tracking-tight text-white">
            Datos Oficiales de la Carta
          </h3>
          <p className="mt-0.5 text-xs text-slate-400">
            Todos los campos son obligatorios. Las reglas de rango y proporción 5:7 están sincronizadas con el backend 1G.
          </p>
        </div>

        {isEditingLocked && status === "uncertain_outcome" && (
          <span className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-950/50 px-3 py-1 text-xs font-semibold text-amber-200">
            <Lock className="h-3.5 w-3.5" aria-hidden="true" />
            Payload bloqueado para reintento idempotente
          </span>
        )}
      </div>

      {/* 1. Nombre de la carta */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <label
            htmlFor={nameInputId}
            className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
          >
            Nombre de la carta <span className="text-red-400">*</span>
          </label>
          <span
            id={nameHintId}
            className={`font-mono text-[11px] ${
              trimmedNameLength > CARD_VALIDATION_CONSTRAINTS.NAME_MAX_LENGTH
                ? "font-bold text-red-400"
                : "text-slate-400"
            }`}
          >
            {trimmedNameLength}/{CARD_VALIDATION_CONSTRAINTS.NAME_MAX_LENGTH} caracteres
          </span>
        </div>

        <input
          id={nameInputId}
          name="name"
          type="text"
          required
          disabled={isEditingLocked}
          value={values.name}
          onChange={(event) => onNameChange(event.currentTarget.value)}
          placeholder="Ej. Lucario Guardián del Aura"
          aria-invalid={Boolean(fieldErrors.name)}
          aria-describedby={fieldErrors.name ? `${nameHintId} ${nameErrorId}` : nameHintId}
          className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
            fieldErrors.name
              ? "border-red-500/70 focus:border-red-400 focus:ring-red-400/40"
              : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
          }`}
        />

        {fieldErrors.name && (
          <p id={nameErrorId} role="alert" className="text-xs font-medium text-red-300">
            {fieldErrors.name}
          </p>
        )}
      </div>

      {/* 2. Costo de energía y 3. Poder base */}
      <div className="grid gap-5 sm:grid-cols-2">
        {/* Costo */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor={costInputId}
              className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
            >
              Costo de energía <span className="text-red-400">*</span>
            </label>
            <span id={costHintId} className="font-mono text-[11px] text-slate-400">
              Entero [{CARD_VALIDATION_CONSTRAINTS.COST_MIN}..{CARD_VALIDATION_CONSTRAINTS.COST_MAX}]
            </span>
          </div>

          <input
            id={costInputId}
            name="cost"
            type="number"
            inputMode="numeric"
            step={1}
            min={CARD_VALIDATION_CONSTRAINTS.COST_MIN}
            max={CARD_VALIDATION_CONSTRAINTS.COST_MAX}
            required
            disabled={isEditingLocked}
            value={rawCostInput}
            onChange={(event) => onCostInputChange(event.currentTarget.value)}
            aria-invalid={Boolean(fieldErrors.cost)}
            aria-describedby={fieldErrors.cost ? `${costHintId} ${costErrorId}` : costHintId}
            className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 font-mono text-sm text-white transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
              fieldErrors.cost
                ? "border-red-500/70 focus:border-red-400 focus:ring-red-400/40"
                : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
            }`}
          />

          {fieldErrors.cost && (
            <p id={costErrorId} role="alert" className="text-xs font-medium text-red-300">
              {fieldErrors.cost}
            </p>
          )}
        </div>

        {/* Poder */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor={powerInputId}
              className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
            >
              Poder base <span className="text-red-400">*</span>
            </label>
            <span id={powerHintId} className="font-mono text-[11px] text-slate-400">
              Entero [{CARD_VALIDATION_CONSTRAINTS.POWER_MIN}..{CARD_VALIDATION_CONSTRAINTS.POWER_MAX}]
            </span>
          </div>

          <input
            id={powerInputId}
            name="power"
            type="number"
            inputMode="numeric"
            step={1}
            min={CARD_VALIDATION_CONSTRAINTS.POWER_MIN}
            max={CARD_VALIDATION_CONSTRAINTS.POWER_MAX}
            required
            disabled={isEditingLocked}
            value={rawPowerInput}
            onChange={(event) => onPowerInputChange(event.currentTarget.value)}
            aria-invalid={Boolean(fieldErrors.power)}
            aria-describedby={fieldErrors.power ? `${powerHintId} ${powerErrorId}` : powerHintId}
            className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 font-mono text-sm text-white transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
              fieldErrors.power
                ? "border-red-500/70 focus:border-red-400 focus:ring-red-400/40"
                : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
            }`}
          />

          {fieldErrors.power && (
            <p id={powerErrorId} role="alert" className="text-xs font-medium text-red-300">
              {fieldErrors.power}
            </p>
          )}
        </div>
      </div>

      {/* 4. Tipo elemental y 5. Rareza */}
      <div className="grid gap-5 sm:grid-cols-2">
        {/* Tipo elemental */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor={typeSelectId}
              className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
            >
              Tipo elemental <span className="text-red-400">*</span>
            </label>
            <span id={typeHintId} className="font-mono text-[11px] text-slate-400">
              Prefijo PKA-{values.card_type}
            </span>
          </div>

          <select
            id={typeSelectId}
            name="card_type"
            disabled={isEditingLocked}
            value={values.card_type}
            onChange={(event) => onCardTypeChange(event.currentTarget.value as CardType)}
            aria-invalid={Boolean(fieldErrors.card_type)}
            aria-describedby={fieldErrors.card_type ? `${typeHintId} ${typeErrorId}` : typeHintId}
            className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 text-sm text-white transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
              fieldErrors.card_type
                ? "border-red-500/70 focus:border-red-400 focus:ring-red-400/40"
                : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
            }`}
          >
            {CARD_TYPES.map((typeCode) => {
              const meta = CARD_TYPE_VISUAL_META[typeCode];
              return (
                <option key={typeCode} value={typeCode}>
                  {typeCode} — {meta.label}
                </option>
              );
            })}
          </select>

          {fieldErrors.card_type && (
            <p id={typeErrorId} role="alert" className="text-xs font-medium text-red-300">
              {fieldErrors.card_type}
            </p>
          )}
        </div>

        {/* Rareza */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor={raritySelectId}
              className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
            >
              Rareza <span className="text-red-400">*</span>
            </label>
            <span id={rarityHintId} className="font-mono text-[11px] text-slate-400">
              Categoría oficial
            </span>
          </div>

          <select
            id={raritySelectId}
            name="rarity"
            disabled={isEditingLocked}
            value={values.rarity}
            onChange={(event) => onRarityChange(event.currentTarget.value as CardRarity)}
            aria-invalid={Boolean(fieldErrors.rarity)}
            aria-describedby={
              fieldErrors.rarity ? `${rarityHintId} ${rarityErrorId}` : rarityHintId
            }
            className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 text-sm text-white transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
              fieldErrors.rarity
                ? "border-red-500/70 focus:border-red-400 focus:ring-red-400/40"
                : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
            }`}
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

          {fieldErrors.rarity && (
            <p id={rarityErrorId} role="alert" className="text-xs font-medium text-red-300">
              {fieldErrors.rarity}
            </p>
          )}
        </div>
      </div>

      {/* 6. Selector de habilidad (GET /api/v1/content/abilities) */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label
            htmlFor={abilitySelectId}
            className="block text-xs font-semibold uppercase tracking-wider text-slate-200"
          >
            Habilidad de catálogo <span className="text-red-400">*</span>
          </label>

          <div className="flex items-center gap-2">
            <span id={abilityHintId} className="font-mono text-[11px] text-slate-400">
              {isLoadingAbilities
                ? "Consultando catálogo..."
                : hasLoadedAbilities
                  ? `${abilities.length} disponibles (incluye HAB-000)`
                  : "Catálogo pendiente"}
            </span>

            <button
              type="button"
              disabled={isLoadingAbilities || isEditingLocked}
              onClick={() => void onReloadAbilities()}
              aria-label="Actualizar lista de habilidades"
              className="inline-flex items-center gap-1 rounded-lg border border-arena-border bg-arena-surface px-2 py-1 text-[11px] font-semibold text-slate-300 transition hover:border-blue-500/50 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                className={`h-3 w-3 ${isLoadingAbilities ? "animate-spin" : ""}`}
                aria-hidden="true"
              />
              <span>Recargar</span>
            </button>
          </div>
        </div>

        {abilitiesError && (
          <AlertBanner
            variant="error"
            title="No se pudieron cargar las habilidades del catálogo"
            description={abilitiesError.detail}
            correlationId={abilitiesError.correlationId}
            actionLabel="Reintentar carga de habilidades"
            onAction={() => void onReloadAbilities()}
          />
        )}

        {hasLoadedAbilities && isAbilitiesEmpty && !abilitiesError && (
          <AlertBanner
            variant="warning"
            title="Catálogo de habilidades vacío"
            description="El servidor devolvió una lista vacía de habilidades. Es necesario contar al menos con HAB-000 para crear una carta."
            actionLabel="Recargar habilidades"
            onAction={() => void onReloadAbilities()}
          />
        )}

        <select
          id={abilitySelectId}
          name="ability_code"
          disabled={
            isEditingLocked ||
            isLoadingAbilities ||
            abilitiesError !== null ||
            (hasLoadedAbilities && isAbilitiesEmpty)
          }
          value={values.ability_code}
          onChange={(event) => onAbilityCodeChange(event.currentTarget.value)}
          aria-invalid={Boolean(fieldErrors.ability_code)}
          aria-describedby={
            fieldErrors.ability_code ? `${abilityHintId} ${abilityErrorId}` : abilityHintId
          }
          className={`w-full rounded-xl border bg-arena-surface/90 px-4 py-2.5 text-sm text-white transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
            fieldErrors.ability_code
              ? "border-red-500/70 focus:border-red-400 focus:ring-red-400/40"
              : "border-arena-border focus:border-arena-accent focus:ring-blue-500/30"
          }`}
        >
          {isLoadingAbilities && abilities.length === 0 && (
            <option value={values.ability_code}>Cargando habilidades desde FastAPI...</option>
          )}

          {!isLoadingAbilities &&
            abilities.length > 0 &&
            !isCurrentAbilityInCatalog &&
            values.ability_code.trim().length > 0 && (
              <option value={values.ability_code} disabled>
                {values.ability_code} — (No disponible en el catálogo actual)
              </option>
            )}

          {abilities.map((ability) => (
            <option key={ability.code} value={ability.code}>
              {ability.code} — {ability.name}
            </option>
          ))}
        </select>

        {fieldErrors.ability_code && (
          <p id={abilityErrorId} role="alert" className="text-xs font-medium text-red-300">
            {fieldErrors.ability_code}
          </p>
        )}
      </div>

      {/* 7. Cargador y validador de imagen (F3) */}
      <div className="pt-1">
        <CardImageUploader
          value={imageSelection}
          onChange={onImageChange}
          onValidationErrorChange={onImageValidationErrorChange}
          disabled={isEditingLocked}
          externalError={fieldErrors.image ?? null}
          customUrlManager={customUrlManager}
          customDimensionsDecoder={customDimensionsDecoder}
        />
      </div>

      {/* Indicador de clave de idempotencia activa cuando hay operación en curso o incierta */}
      {activeIdempotencyKey && (status === "submitting" || status === "uncertain_outcome") && (
        <div
          data-testid="active-idempotency-indicator"
          className="rounded-xl border border-arena-border bg-arena-surface/60 px-3.5 py-2.5 text-xs text-slate-300 flex flex-wrap items-center justify-between gap-2"
        >
          <span className="font-semibold text-slate-200">
            Idempotency-Key vinculada a esta operación:
          </span>
          <code className="font-mono text-[11px] text-blue-300 select-all">
            {activeIdempotencyKey}
          </code>
        </div>
      )}

      {/* Botonera de acciones según el estado de la máquina */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-arena-border/70 pt-5">
        {status === "uncertain_outcome" ? (
          <>
            <button
              type="button"
              onClick={onAbandonUncertainOperation}
              className="inline-flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-xs font-semibold text-amber-200 transition hover:bg-amber-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
            >
              <Unlock className="h-4 w-4" aria-hidden="true" />
              <span>Descartar intento incierto y editar borrador</span>
            </button>

            <button
              type="button"
              onClick={() => void onRetryPendingOperation()}
              className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-bold text-slate-950 shadow-lg shadow-amber-500/20 transition hover:bg-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              <span>Reintentar operación pendiente</span>
            </button>
          </>
        ) : status === "success" ? (
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-emerald-300 font-medium">
              La carta ya fue confirmada. Para registrar otra carta con una nueva clave de idempotencia:
            </p>
            <button
              type="button"
              onClick={onStartNewCard}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-emerald-600/25 transition hover:bg-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              <PlusCircle className="h-4 w-4" aria-hidden="true" />
              <span>Crear otra carta</span>
            </button>
          </div>
        ) : (
          <>
            <button
              type="button"
              disabled={isEditingLocked}
              onClick={onStartNewCard}
              className="inline-flex items-center gap-2 rounded-xl border border-arena-border bg-arena-surface px-4 py-2.5 text-xs font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Reiniciar formulario</span>
            </button>

            <button
              type="submit"
              disabled={isSubmitDisabled}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-600/25 transition hover:from-blue-500 hover:to-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  <span>Guardando carta en catálogo...</span>
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" aria-hidden="true" />
                  <span>Crear Carta Oficial</span>
                  <Sparkles className="h-3.5 w-3.5 opacity-80" aria-hidden="true" />
                </>
              )}
            </button>
          </>
        )}
      </div>
    </form>
  );
}
