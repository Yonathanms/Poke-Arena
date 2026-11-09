/**
 * Experiencia interactiva de apertura del paquete inicial de jugador (US 3.1.1).
 *
 * Responsabilidades:
 * 1. Presentar el sobre sellado de bienvenida cuando el backend indica `READY_TO_OPEN`,
 *    resumiendo el contenido garantizado (15 cartas comunes + 1.000 cubos).
 * 2. Exponer el botón de confirmación de apertura (`onOpenPack`) protegido contra doble clic.
 * 3. Indicar el estado de procesamiento durante `OPENING` con retroalimentación visual accesible.
 * 4. Presentar la cuadrícula de revelación de las 15 cartas comunes recibidas (`retainedCards`)
 *    tras la confirmación en el servidor.
 * 5. Destacar la concesión del bono inicial de 1.000 cubos de energía (primer movimiento SQL).
 * 6. Ofrecer el botón de continuación (`onCompleteReveal`) para avanzar a la vista principal.
 * 7. Respetar accesibilidad, navegación por teclado y `prefers-reduced-motion`.
 */

import React from "react";
import {
  ArrowRight,
  Boxes,
  CheckCircle2,
  Coins,
  Gift,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import type {
  InitialPackCardDTO,
  InitialPackErrorInfo,
} from "../types/initial_pack.types";
import { InitialPackCardTile } from "./InitialPackCardTile";

export interface PackOpeningExperienceProps {
  readonly phase: "READY_TO_OPEN" | "OPENING" | "REVEALED";
  readonly retainedCards: readonly InitialPackCardDTO[];
  readonly grantedCubes: number;
  readonly isOpening: boolean;
  readonly error: InitialPackErrorInfo | null;
  readonly onOpenPack: () => Promise<unknown> | void;
  readonly onCompleteReveal: () => void;
  readonly onClearError?: () => void;
}

export function PackOpeningExperience({
  phase,
  retainedCards,
  grantedCubes,
  isOpening,
  error,
  onOpenPack,
  onCompleteReveal,
  onClearError,
}: PackOpeningExperienceProps): React.ReactElement {
  const isRevealed = phase === "REVEALED";

  // ---------------------------------------------------------------------------
  // FASE 2: Revelación de las 15 cartas y bono de 1.000 cubos (tras confirmar apertura)
  // ---------------------------------------------------------------------------
  if (isRevealed) {
    return (
      <div className="flex flex-col gap-8 pb-12 animate-in fade-in duration-300 motion-reduce:animate-none">
        {/* Cabecera de felicitación y confirmación */}
        <section
          aria-labelledby="pack-unlocked-title"
          className="relative overflow-hidden rounded-3xl border border-arena-border bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 p-6 sm:p-8 shadow-2xl"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div className="flex items-start sm:items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-emerald-500/40 bg-gradient-to-tr from-emerald-600/30 to-teal-500/20 shadow-lg shadow-emerald-500/20">
                <CheckCircle2 className="h-7 w-7 text-emerald-400" aria-hidden="true" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-emerald-300">
                    Apertura Confirmada
                  </span>
                </div>
                <h2
                  id="pack-unlocked-title"
                  className="mt-1 text-2xl font-black tracking-tight text-white sm:text-3xl"
                >
                  ¡Has recibido 15 cartas y 1.000 cubos!
                </h2>
                <p className="mt-1 text-xs sm:text-sm text-slate-300">
                  Tu colección de bienvenida y tu balance inicial están listos para la batalla.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onCompleteReveal}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-500 px-6 py-3.5 text-sm font-bold text-white shadow-xl shadow-blue-600/30 transition hover:from-blue-500 hover:to-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              <span>Continuar a mi panel</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </section>

        {/* Tarjeta destacada del Bono de Cubos de Energía */}
        <section
          aria-labelledby="cubes-grant-title"
          className="rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-950/30 via-slate-900 to-slate-900 p-5 shadow-lg"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-amber-500/40 bg-amber-500/20 shadow-md shadow-amber-500/20">
                <Coins className="h-6 w-6 text-amber-400" aria-hidden="true" />
              </div>
              <div>
                <h3 id="cubes-grant-title" className="text-sm font-bold text-white">
                  +{grantedCubes.toLocaleString()} Cubos de Energía Otorgados
                </h3>
                <p className="text-xs text-slate-400">
                  Añadidos a tu saldo inicial para comenzar a jugar y participar en la arena.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-amber-300/90 bg-amber-950/40 px-3 py-1.5 rounded-xl border border-amber-500/20 self-start sm:self-auto">
              <span>SALDO INICIAL: {grantedCubes.toLocaleString()} CUBOS</span>
            </div>
          </div>
        </section>

        {/* Cuadrícula de las 15 cartas comunes reveladas */}
        <section aria-labelledby="cards-grid-title" className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Boxes className="h-5 w-5 text-blue-400" aria-hidden="true" />
              <h3 id="cards-grid-title" className="text-lg font-bold text-white">
                Cartas Comunes Recibidas ({retainedCards.length}/15)
              </h3>
            </div>
            <span className="text-xs text-slate-400">
              Listas para construir tu primer mazo de 12 cartas distintas
            </span>
          </div>

          <div
            role="list"
            aria-label="Cuadrícula de 15 cartas iniciales comunes"
            className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
          >
            {retainedCards.map((card) => (
              <div key={card.id} role="listitem">
                <InitialPackCardTile card={card} />
              </div>
            ))}
          </div>
        </section>

        {/* Botón flotante inferior para continuar */}
        <div className="flex justify-center pt-4">
          <button
            type="button"
            onClick={onCompleteReveal}
            className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 px-8 py-3.5 text-sm font-bold text-white shadow-xl shadow-blue-600/30 transition hover:from-blue-500 hover:to-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <span>Ir a Mi Panel de Jugador</span>
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // FASE 1: Paquete sellado listo para abrir (READY_TO_OPEN / OPENING)
  // ---------------------------------------------------------------------------
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 py-8 text-slate-100 animate-in fade-in duration-200 motion-reduce:animate-none">
      <div className="w-full max-w-xl">
        {/* Banner de error de apertura si ocurrió un fallo recuperable (ej. 503) */}
        {error && (
          <div className="mb-6">
            <AlertBanner
              variant="error"
              title={error.title}
              description={`${error.detail} ${error.userGuidance}`}
              onDismiss={onClearError}
            />
          </div>
        )}

        <div className="relative overflow-hidden rounded-3xl border border-arena-border bg-slate-900/90 p-8 shadow-2xl shadow-black/60 backdrop-blur-md">
          {/* Fondo sutil decorativo */}
          <div
            className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-blue-500/10 blur-3xl"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute -bottom-24 -left-24 h-64 w-64 rounded-full bg-amber-500/10 blur-3xl"
            aria-hidden="true"
          />

          <div className="relative flex flex-col items-center text-center">
            {/* Ícono animado del sobre sellado */}
            <div className="relative flex h-24 w-24 items-center justify-center rounded-3xl border border-amber-500/40 bg-gradient-to-tr from-amber-600/30 via-indigo-600/20 to-blue-600/30 shadow-2xl shadow-amber-500/20 transition-transform duration-300 hover:scale-105">
              <Gift className="h-12 w-12 text-amber-300" aria-hidden="true" />
              <div className="absolute -top-1.5 -right-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-amber-400 text-slate-950 shadow-md">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
              </div>
            </div>

            <div className="mt-6">
              <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-blue-300">
                Paquete Inicial de Bienvenida
              </span>
            </div>

            <h2 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">
              Tu paquete está listo
            </h2>

            <p className="mt-3 text-sm leading-relaxed text-slate-300 max-w-md">
              Como nuevo entrenador de Poké-Arena, se te ha otorgado un paquete inicial
              con cartas comunes y cubos de energía listos para ser desbloqueados.
            </p>

            {/* Resumen del contenido sellado */}
            <div className="mt-6 w-full space-y-2.5 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-left text-xs">
              <div className="flex items-center justify-between py-1">
                <span className="font-medium text-slate-300 flex items-center gap-2">
                  <Boxes className="h-4 w-4 text-blue-400" aria-hidden="true" />
                  15 Cartas de Rareza COMÚN
                </span>
                <span className="font-mono text-slate-400">Sorteo Servidor</span>
              </div>
              <div className="flex items-center justify-between border-t border-slate-800/80 pt-2 py-1">
                <span className="font-medium text-slate-300 flex items-center gap-2">
                  <Coins className="h-4 w-4 text-amber-400" aria-hidden="true" />
                  1.000 Cubos de Energía
                </span>
                <span className="font-mono text-emerald-400 font-semibold">+1.000 CUBOS</span>
              </div>
              <div className="flex items-center justify-between border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
                <span>Condición de juego</span>
                <span className="text-slate-300">Listo para construir mazo de 12 cartas</span>
              </div>
            </div>

            {/* Botón de apertura */}
            <div className="mt-8 w-full flex flex-col items-center gap-3">
              <button
                type="button"
                disabled={isOpening}
                onClick={() => void onOpenPack()}
                aria-busy={isOpening}
                className="w-full flex items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 px-8 py-4 text-base font-extrabold text-slate-950 shadow-xl shadow-amber-500/25 transition-all hover:scale-[1.02] hover:shadow-amber-500/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 disabled:scale-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isOpening ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin text-slate-950" aria-hidden="true" />
                    <span>Abriendo tu paquete...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-5 w-5 text-slate-950" aria-hidden="true" />
                    <span>Abrir Paquete Inicial</span>
                  </>
                )}
              </button>

              {error && error.isRetryable && !isOpening && (
                <button
                  type="button"
                  onClick={() => void onOpenPack()}
                  className="inline-flex items-center gap-1.5 text-xs text-amber-400 hover:text-amber-300 transition-colors"
                >
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Reintentar confirmación de apertura</span>
                </button>
              )}
            </div>

            <p className="mt-4 text-[11px] text-slate-500">
              Entrega segura y verificada por el servidor de Poké-Arena.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
