/**
 * Pantalla principal del caso de uso administrativo 2.1.1 — Crear Carta (`CreateCardScreen.tsx`).
 *
 * Responsabilidades:
 * 1. Ensamblar `CardForm`, `CardPreviewCard`, `useAbilities`, `useCreateCard` y `CatalogListScreen`.
 * 2. Sincronizar el catálogo reactivo de habilidades (`GET /api/v1/content/abilities`) con
 *    el validador del formulario para detectar selecciones obsoletas tras una recarga.
 * 3. Presentar banners accesibles de confirmación (`201 Created` con `code`, `id`, `image_id`,
 *    `operation_id`, `image_status: READY`), resultados inciertos (`500`, `503`, `409 en_curso`,
 *    error de red) con acción directa de replay idempotente, y errores definitivos RFC 7807
 *    con su `correlation_id`.
 * 4. Ofrecer diseño responsivo de dos columnas en escritorio (formulario + vista previa 5:7)
 *    y una columna en dispositivos móviles.
 */

import React, { useEffect, useState } from "react";
import { CheckCircle2, FilePlus2, History, Sparkles } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { CardForm } from "../components/CardForm";
import { CardPreviewCard } from "../components/CardPreviewCard";
import { useAbilities } from "../hooks/useAbilities";
import { useCardMetadata } from "../hooks/useCardMetadata";
import {
  useCreateCard,
  type CreateCardController,
} from "../hooks/useCreateCard";
import type {
  ImageDimensionsDecoder,
  ObjectUrlManager,
} from "../validation/card-validation";
import { CatalogListScreen } from "./CatalogListScreen";

export interface CreateCardScreenProps {
  readonly controller?: CreateCardController;
  readonly fetchImpl?: typeof fetch;
  readonly customUrlManager?: ObjectUrlManager;
  readonly customDimensionsDecoder?: ImageDimensionsDecoder;
}

type ActiveCatalogTab = "create" | "session_history";

export function CreateCardScreen({
  controller,
  fetchImpl,
  customUrlManager,
  customDimensionsDecoder,
}: CreateCardScreenProps = {}): React.ReactElement {
  const [activeTab, setActiveTab] = useState<ActiveCatalogTab>("create");

  const {
    abilities,
    isLoading: isLoadingAbilities,
    hasLoaded: hasLoadedAbilities,
    isEmpty: isAbilitiesEmpty,
    error: abilitiesError,
    reload: reloadAbilities,
  } = useAbilities({ fetchImpl });

  const { types, rarities } = useCardMetadata({ fetchImpl });

  const {
    status,
    values,
    rawCostInput,
    rawPowerInput,
    imageSelection,
    fieldErrors,
    activeIdempotencyKey,
    createdCard,
    lastCorrelationId,
    errorInfo,
    sessionHistory,
    isSubmitting,
    isEditingLocked,
    setName,
    setCostInput,
    setPowerInput,
    setCardType,
    setRarity,
    setAbilityCode,
    setImageSelection,
    setImageValidationError,
    syncAvailableAbilities,
    submit,
    retryPendingOperation,
    abandonUncertainOperation,
    startNewCard,
    dismissErrorBanner,
  } = useCreateCard({ controller, fetchImpl });

  useEffect(() => {
    if (hasLoadedAbilities) {
      syncAvailableAbilities(abilities, true);
    }
  }, [abilities, hasLoadedAbilities, syncAvailableAbilities]);

  return (
    <div className="space-y-6">
      {/* Encabezado del módulo de Catálogo y pestañas de navegación interna */}
      <div className="flex flex-col justify-between gap-4 rounded-2xl glass-card border border-arena-border p-5 sm:flex-row sm:items-center sm:px-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/15 text-blue-400">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white sm:text-xl">
              Módulo de Catálogo — Crear Carta (2.1.1)
            </h1>
            <p className="text-xs text-slate-400">
              Registro transaccional con validación 5:7, almacenamiento GridFS e idempotencia segura.
            </p>
          </div>
        </div>

        {/* Selector de vista dentro del módulo de catálogo */}
        <div
          role="tablist"
          aria-label="Vistas del módulo de catálogo"
          className="inline-flex rounded-xl border border-arena-border bg-arena-bg/80 p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "create"}
            onClick={() => setActiveTab("create")}
            className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
              activeTab === "create"
                ? "bg-arena-accent text-white shadow-sm"
                : "text-slate-300 hover:text-white"
            }`}
          >
            <FilePlus2 className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Crear Carta</span>
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "session_history"}
            onClick={() => setActiveTab("session_history")}
            className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
              activeTab === "session_history"
                ? "bg-arena-accent text-white shadow-sm"
                : "text-slate-300 hover:text-white"
            }`}
          >
            <History className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Confirmadas en Sesión</span>
            <span className="rounded-full bg-white/15 px-1.5 py-0.2 font-mono text-[11px]">
              {sessionHistory.length}
            </span>
          </button>
        </div>
      </div>

      {activeTab === "session_history" ? (
        <CatalogListScreen
          entries={sessionHistory}
          onNavigateToCreate={() => setActiveTab("create")}
        />
      ) : (
        <div className="space-y-6">
          {/* Banner de Resultado Incierto (500, 503 commit_incierto, 409 en_curso, fallo de red) */}
          {status === "uncertain_outcome" && errorInfo && (
            <AlertBanner
              variant="warning"
              title={errorInfo.title}
              description={`${errorInfo.detail} ${errorInfo.userGuidance}`}
              correlationId={errorInfo.correlationId}
              actionLabel="Reintentar operación con la misma Idempotency-Key"
              onAction={() => void retryPendingOperation()}
            />
          )}

          {/* Banner de Error Definitivo (422, 413, 415, 403, 404, 409 conflicto_idempotencia) */}
          {status === "definite_error" && errorInfo && (
            <AlertBanner
              variant="error"
              title={errorInfo.title}
              description={`${errorInfo.detail} ${errorInfo.userGuidance}`}
              correlationId={errorInfo.correlationId}
              onDismiss={dismissErrorBanner}
            />
          )}

          {/* Banner de Éxito (201 Created) con resumen completo y acción "Crear otra carta" */}
          {status === "success" && createdCard && (
            <div data-testid="card-created-success-banner" className="space-y-3">
              <AlertBanner
                variant="success"
                title={`Carta creada exitosamente — Código oficial: ${createdCard.code}`}
                description={`Estado de imagen confirmado: ${createdCard.image_status} (original 5:7 y miniatura WebP 200×280 verificadas en GridFS). ID Carta: ${createdCard.id} · ID Imagen: ${createdCard.image_id} · Operación: ${createdCard.operation_id}.`}
                correlationId={lastCorrelationId}
                actionLabel="Crear otra carta"
                onAction={startNewCard}
              />

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-4 py-2.5 text-xs text-emerald-200">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" aria-hidden="true" />
                  <span>
                    La operación quedó cerrada para la clave{" "}
                    <code className="font-mono text-emerald-300">{activeIdempotencyKey}</code>.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("session_history")}
                  className="font-semibold text-emerald-300 underline underline-offset-2 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 rounded"
                >
                  Ver en registro de la sesión ({sessionHistory.length})
                </button>
              </div>
            </div>
          )}

          {/* Disposición de 2 columnas en escritorio y 1 columna en móvil */}
          <div className="grid gap-8 lg:grid-cols-[1fr_380px] items-start">
            <CardForm
              values={values}
              rawCostInput={rawCostInput}
              rawPowerInput={rawPowerInput}
              imageSelection={imageSelection}
              fieldErrors={fieldErrors}
              status={status}
              isSubmitting={isSubmitting}
              isEditingLocked={isEditingLocked}
              activeIdempotencyKey={activeIdempotencyKey}
              types={types}
              rarities={rarities}
              abilities={abilities}
              isLoadingAbilities={isLoadingAbilities}
              hasLoadedAbilities={hasLoadedAbilities}
              isAbilitiesEmpty={isAbilitiesEmpty}
              abilitiesError={abilitiesError}
              onNameChange={setName}
              onCostInputChange={setCostInput}
              onPowerInputChange={setPowerInput}
              onCardTypeChange={setCardType}
              onRarityChange={setRarity}
              onAbilityCodeChange={setAbilityCode}
              onImageChange={setImageSelection}
              onImageValidationErrorChange={setImageValidationError}
              onReloadAbilities={reloadAbilities}
              onSubmit={submit}
              onRetryPendingOperation={retryPendingOperation}
              onAbandonUncertainOperation={abandonUncertainOperation}
              onStartNewCard={startNewCard}
              customUrlManager={customUrlManager}
              customDimensionsDecoder={customDimensionsDecoder}
            />

            <div className="lg:sticky lg:top-24 rounded-2xl glass-card border border-arena-border p-5 sm:p-6">
              <CardPreviewCard
                values={values}
                abilities={abilities}
                imageSelection={imageSelection}
                status={status}
                createdCard={createdCard}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
