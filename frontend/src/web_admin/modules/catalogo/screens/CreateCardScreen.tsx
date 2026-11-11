/**
 * Pantalla principal para Crear Carta en el módulo administrativo de Catálogo (US 2.1.1).
 * Ensambla el formulario de creación y el panel de previsualización en vivo.
 */

import React, { useEffect, useState } from "react";
import { CheckCircle2, Layers, X } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { CardForm } from "../components/CardForm";
import { CardPreviewCard } from "../components/CardPreviewCard";
import { useAbilities } from "../hooks/useAbilities";
import { useCardMetadata } from "../hooks/useCardMetadata";
import { useCreateCard } from "../hooks/useCreateCard";

export function CreateCardScreen(): React.ReactElement {
  const {
    abilities,
    isLoading: isLoadingAbilities,
    error: abilitiesError,
    reload: reloadAbilities,
  } = useAbilities();

  const { types, rarities } = useCardMetadata();

  const {
    values,
    imageSelection,
    errors,
    isSubmitting,
    serverError,
    successCard,
    handleChange,
    handleImageChange,
    submit,
    reset,
    dismissServerError,
  } = useCreateCard();

  const [toastCardCode, setToastCardCode] = useState<string | null>(null);

  useEffect(() => {
    if (successCard) {
      setToastCardCode(successCard.code);
      reset();
      const timer = window.setTimeout(() => {
        setToastCardCode(null);
      }, 3500);
      return () => window.clearTimeout(timer);
    }
  }, [successCard, reset]);

  const handleSubmit = (): void => {
    const availableCodes = abilities.map((a) => a.code);
    void submit(availableCodes);
  };

  return (
    <div className="space-y-6">
      {/* Toast flotante no bloqueante */}
      {toastCardCode && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-20 right-6 z-50 max-w-sm rounded-2xl border border-emerald-500/40 bg-[#0F172A]/95 backdrop-blur-md p-4 shadow-[0_12px_32px_rgba(0,0,0,0.6)] animate-toast-in flex items-start gap-3"
        >
          <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-emerald-300">
              ✓ Carta creada correctamente
            </p>
            <p className="mt-0.5 text-xs text-slate-300">
              <span className="font-mono font-semibold text-white">{toastCardCode}</span> ya está disponible en el catálogo.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setToastCardCode(null)}
            className="text-slate-400 hover:text-white transition"
            aria-label="Cerrar aviso"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex items-center gap-3.5 glass-card p-5 sm:px-6">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/15 text-blue-400">
          <Layers className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white sm:text-xl">
            Crear Carta Oficial
          </h1>
          <p className="text-xs text-slate-400">
            Registra una carta en el catálogo con validación 5:7 y previsualización en tiempo real.
          </p>
        </div>
      </div>

      {serverError && (
        <AlertBanner
          variant="error"
          title="No se pudo crear la carta"
          description={serverError}
          onDismiss={dismissServerError}
        />
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_380px] items-start">
        <CardForm
          values={values}
          errors={errors}
          imageSelection={imageSelection}
          types={types}
          rarities={rarities}
          abilities={abilities}
          isLoadingAbilities={isLoadingAbilities}
          abilitiesError={abilitiesError}
          isSubmitting={isSubmitting}
          disabled={false}
          onChange={handleChange}
          onImageChange={handleImageChange}
          onReloadAbilities={() => void reloadAbilities()}
          onSubmit={handleSubmit}
          onReset={reset}
        />

        <div className="lg:sticky lg:top-24 glass-card p-5 sm:p-6">
          <CardPreviewCard
            values={values}
            abilities={abilities}
            imageSelection={imageSelection}
            isSubmitting={isSubmitting}
            createdCard={successCard}
          />
        </div>
      </div>
    </div>
  );
}
