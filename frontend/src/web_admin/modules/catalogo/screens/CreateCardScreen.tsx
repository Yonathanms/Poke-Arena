/**
 * Pantalla principal para Crear Carta en el módulo administrativo de Catálogo (US 2.1.1).
 * Ensambla el formulario de creación y el panel de previsualización en vivo.
 */

import React from "react";
import { Sparkles } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { CardForm } from "../components/CardForm";
import { CardPreviewCard } from "../components/CardPreviewCard";
import { useAbilities } from "../hooks/useAbilities";
import { useCreateCard } from "../hooks/useCreateCard";

export function CreateCardScreen(): React.ReactElement {
  const {
    abilities,
    isLoading: isLoadingAbilities,
    error: abilitiesError,
    reload: reloadAbilities,
  } = useAbilities();

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

  const handleSubmit = (): void => {
    const availableCodes = abilities.map((a) => a.code);
    void submit(availableCodes);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3.5 rounded-2xl glass-card border border-arena-border p-5 sm:px-6">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/15 text-blue-400">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
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

      {successCard && (
        <AlertBanner
          variant="success"
          title={`¡Carta creada exitosamente! Código asignado: ${successCard.code}`}
          description={`La carta quedó disponible en el catálogo (estado de imagen: ${successCard.image_status}).`}
          actionLabel="Crear otra carta"
          onAction={reset}
        />
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_380px] items-start">
        <CardForm
          values={values}
          errors={errors}
          imageSelection={imageSelection}
          abilities={abilities}
          isLoadingAbilities={isLoadingAbilities}
          abilitiesError={abilitiesError}
          isSubmitting={isSubmitting}
          disabled={successCard !== null}
          onChange={handleChange}
          onImageChange={handleImageChange}
          onReloadAbilities={() => void reloadAbilities()}
          onSubmit={handleSubmit}
          onReset={reset}
        />

        <div className="lg:sticky lg:top-24 rounded-2xl glass-card border border-arena-border p-5 sm:p-6">
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
