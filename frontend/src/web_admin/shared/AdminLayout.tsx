/**
 * Layout principal del portal de Administración (`web_admin`).
 *
 * Responsabilidades:
 * - Presentar el encabezado institucional de Poké-Arena con la paleta `arena` y fuente `Outfit`.
 * - Mostrar el estado de autenticación (`PLATFORM_ADMIN`), el identificador público del
 *   administrador (`userId`) y el tiempo de sesión restante (`MM:SS`).
 * - Exponer la acción de cierre de sesión delegada al hook/servicio correspondiente.
 * - Alojar la pantalla administrativa de Catálogo (`CreateCardScreen` por defecto) sin
 *   realizar peticiones HTTP ni exponer tokens en el DOM.
 */

import React from "react";
import { Clock, Loader2, LogOut, ShieldCheck, Sparkles } from "lucide-react";
import type { ActiveSessionSnapshot } from "../modules/auth/types/auth.types";
import { CreateCardScreen } from "../modules/catalogo/screens/CreateCardScreen";

export interface AdminLayoutProps {
  readonly session: ActiveSessionSnapshot;
  readonly remainingSeconds: number;
  readonly isLoggingOut: boolean;
  readonly onLogout: () => Promise<unknown> | void;
  readonly children?: React.ReactNode;
}

/**
 * Formatea segundos restantes en `MM:SS` para presentación accesible en la barra superior.
 */
export function formatRemainingSessionTime(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function AdminLayout({
  session,
  remainingSeconds,
  isLoggingOut,
  onLogout,
  children,
}: AdminLayoutProps): React.ReactElement {
  const isExpiringSoon = remainingSeconds > 0 && remainingSeconds <= 120;
  const formattedTime = formatRemainingSessionTime(remainingSeconds);

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100 flex flex-col">
      {/* Barra superior administrativa */}
      <header className="sticky top-0 z-40 glass-panel border-b border-arena-border/80">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
          {/* Identidad de Poké-Arena y del portal */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 shadow-lg shadow-blue-500/20">
              <Sparkles className="h-5 w-5 text-white" aria-hidden="true" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-lg font-bold tracking-tight text-white">Poké-Arena</span>
                <span className="rounded-full border border-blue-500/30 bg-blue-500/20 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-blue-300">
                  Portal Administrativo
                </span>
              </div>
              <p className="text-xs text-slate-400">Gestión de Catálogo de Cartas</p>
            </div>
          </div>

          {/* Estado de sesión, rol, expiración y botón de salida */}
          <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
            <div
              aria-label="Estado de sesión administrativa"
              className="flex items-center gap-2 rounded-xl border border-arena-border bg-arena-surface/80 px-3 py-1.5 text-xs"
            >
              <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" aria-hidden="true" />
              <span className="font-semibold text-emerald-300">{session.role}</span>
              <span className="text-slate-500" aria-hidden="true">
                ·
              </span>
              <span className="font-mono text-slate-300 truncate max-w-[140px]" title={session.userId}>
                ID: {session.userId}
              </span>
            </div>

            <div
              role="timer"
              aria-label="Tiempo restante de sesión"
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-mono ${
                isExpiringSoon
                  ? "border-amber-500/40 bg-amber-950/40 text-amber-200"
                  : "border-arena-border bg-arena-surface/80 text-slate-300"
              }`}
            >
              <Clock
                className={`h-3.5 w-3.5 shrink-0 ${
                  isExpiringSoon ? "text-amber-400" : "text-blue-400"
                }`}
                aria-hidden="true"
              />
              <span>Sesión: {formattedTime}</span>
            </div>

            <button
              type="button"
              disabled={isLoggingOut}
              onClick={() => void onLogout()}
              className="inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-3.5 py-1.5 text-xs font-semibold text-red-200 transition hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoggingOut ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  <span>Cerrando...</span>
                </>
              ) : (
                <>
                  <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Cerrar sesión</span>
                </>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Área principal de contenido */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        {children ?? <CreateCardScreen />}
      </main>
    </div>
  );
}
