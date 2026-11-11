/**
 * Pantalla orquestadora del flujo de onboarding de jugador (US 3.1.1).
 *
 * Responsabilidades:
 * 1. Consumir el hook de estado `useInitialPackOnboarding` desarrollado en P1.
 * 2. Representar cada fase del onboarding (`LOADING`, `PENDING_CATALOG`,
 *    `READY_TO_OPEN`, `OPENING`, `REVEALED`, `ERROR`).
 * 3. Coordinar los componentes visuales `PendingCatalogNotice`, `PackOpeningExperience`
 *    e `InitialPackCardTile`.
 * 4. Permitir la transición fluida hacia `VistaPrincipalScreen` una vez que la apertura
 *    del paquete ha sido confirmada (`COMPLETED`).
 * 5. Gestionar la acción de cierre de sesión (`onLogout`) en cualquier momento del flujo.
 */

import React from "react";
import { Loader2, LogOut, RefreshCw } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { VistaPrincipalScreen } from "../../vista_principal/screens/VistaPrincipalScreen";
import { PackOpeningExperience } from "../components/PackOpeningExperience";
import { PendingCatalogNotice } from "../components/PendingCatalogNotice";
import {
  useInitialPackOnboarding,
  type InitialPackOnboardingController,
} from "../hooks/useInitialPackOnboarding";
import pokemonIcon from "../../../../images/icons/icono_pokemon.png";

export interface InitialPackOnboardingScreenProps {
  readonly onLogout: () => void | Promise<unknown>;
  readonly isLoggingOut?: boolean;
  readonly onCompleted?: () => void;
  readonly controller?: InitialPackOnboardingController;
  readonly fetchImpl?: typeof fetch;
}

export function InitialPackOnboardingScreen({
  onLogout,
  isLoggingOut = false,
  onCompleted,
  controller,
  fetchImpl,
}: InitialPackOnboardingScreenProps): React.ReactElement {
  const {
    phase,
    backendState,
    retainedCards,
    grantedCubes,
    isLoading,
    isOpening,
    isPendingCatalog,
    isCompleted,
    error,
    openPack,
    refreshStatus,
    completeReveal,
    clearError,
  } = useInitialPackOnboarding({ controller, fetchImpl });

  // ---------------------------------------------------------------------------
  // 1. ESTADO COMPLETED: El jugador completó el onboarding (o recargó con paquete ya abierto)
  // ---------------------------------------------------------------------------
  if (isCompleted) {
    if (onCompleted) {
      onCompleted();
    }
    return (
      <VistaPrincipalScreen
        onLogout={() => void onLogout()}
        isLoggingOut={isLoggingOut}
      />
    );
  }

  // ---------------------------------------------------------------------------
  // 2. ESTADO LOADING: Consultando GET /player/initial-pack al iniciar
  // ---------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center poke-arena-bg px-4 py-12 text-slate-100">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-blue-500/40 bg-gradient-to-tr from-blue-600/30 to-indigo-600/20 shadow-xl shadow-blue-500/20">
            <Loader2 className="h-8 w-8 animate-spin text-blue-400" aria-hidden="true" />
          </div>
          <h2 className="text-xl font-bold tracking-tight text-white">
            Preparando tu colección inicial
          </h2>
          <p className="max-w-xs text-xs text-slate-300">
            Preparando tu paquete de bienvenida de Poké-Arena...
          </p>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 3. ESTADO ERROR CRÍTICO (ej. 401 sesión expirada o fallo general de red inicial)
  // ---------------------------------------------------------------------------
  if (phase === "ERROR" && backendState === null) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center poke-arena-bg px-4 py-12 text-slate-100">
        <div className="w-full max-w-lg glass-card p-6">
          <AlertBanner
            variant="error"
            title={error?.title || "Error en Colección Inicial"}
            description={
              error
                ? `${error.detail} ${error.userGuidance}`
                : "No fue posible verificar tu colección inicial."
            }
          />
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            {error && error.isRetryable && (
              <button
                type="button"
                onClick={() => void refreshStatus()}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-xs shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                <span>Reintentar</span>
              </button>
            )}
            <button
              type="button"
              disabled={isLoggingOut}
              onClick={() => void onLogout()}
              className="inline-flex items-center gap-2 bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-4 py-2 text-xs font-semibold transition-all disabled:opacity-50"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span>{isLoggingOut ? "Cerrando..." : "Cerrar Sesión"}</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 4. FLUJO PRINCIPAL: Barra superior común y contenido según estado
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen poke-arena-bg text-slate-100 flex flex-col">
      {/* Barra superior del portal de jugador en onboarding */}
      <header className="sticky top-0 z-40 glass-panel border-b border-white/10">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#0F172A]/90 border border-white/10 p-1.5 shadow-lg shadow-blue-500/20">
              <img
                src={pokemonIcon}
                alt="Poké-Arena"
                className="h-6 w-6 object-contain drop-shadow-[0_0_8px_rgba(239,68,68,0.4)]"
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-black tracking-wider text-white">Poké-Arena</span>
                <span className="rounded-full border border-blue-500/30 bg-blue-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-300">
                  Portal Jugador
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">Bienvenida y Colección Inicial</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={isLoggingOut}
              onClick={() => void onLogout()}
              className="inline-flex items-center gap-2 bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-4 py-2 text-xs font-semibold transition-all disabled:opacity-50"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{isLoggingOut ? "Cerrando..." : "Cerrar sesión"}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Contenido principal según fase del onboarding */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        {isPendingCatalog ? (
          <PendingCatalogNotice onLogout={onLogout} isLoggingOut={isLoggingOut} />
        ) : (
          <PackOpeningExperience
            phase={phase === "REVEALED" ? "REVEALED" : isOpening ? "OPENING" : "READY_TO_OPEN"}
            retainedCards={retainedCards}
            grantedCubes={grantedCubes}
            isOpening={isOpening}
            error={error}
            onOpenPack={openPack}
            onCompleteReveal={completeReveal}
            onClearError={clearError}
          />
        )}
      </main>
    </div>
  );
}
