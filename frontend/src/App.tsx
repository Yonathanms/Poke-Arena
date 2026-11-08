/**
 * Raíz de la aplicación Frontend de Poké-Arena (`web-admin` y `web-player`).
 *
 * Responsabilidades:
 * 1. Coordinar el ciclo de autenticación administrativa a través de `useAdminSession`.
 * 2. Restringir el acceso a `AdminLayout` y `CreateCardScreen` exclusivamente cuando
 *    existe una sesión activa con rol `PLATFORM_ADMIN`.
 * 3. Si una sesión expira o se invalida por `401` después de que el administrador ya
 *    había ingresado al área de trabajo, mantener el árbol del área de trabajo montado
 *    en memoria (oculto e inerte con `hidden` / `aria-hidden`) mientras presenta el
 *    formulario de reautenticación, preservando el borrador de Crear Carta y cualquier
 *    `Idempotency-Key` pendiente sin exponer contenido protegido ni usar `localStorage`.
 * 4. Permitir la visualización del catálogo de jugadores (`SearchCardsScreen`) mediante
 *    el selector de vista o ruta de jugador (`?view=player` o `/player`).
 */

import React, { useEffect, useState } from "react";
import { AdminLoginForm } from "./web-admin/modules/auth/components/AdminLoginForm";
import { useAdminSession } from "./web-admin/modules/auth/hooks/useAdminSession";
import { CreateCardScreen } from "./web-admin/modules/catalogo/screens/CreateCardScreen";
import { SearchCardsScreen } from "./web-player/modules/catalogo/screens/SearchCardsScreen";
import { AdminLayout } from "./web-admin/shared/AdminLayout";

export interface AppProps {
  readonly children?: React.ReactNode;
}

export default function App({ children }: AppProps = {}): React.ReactElement {
  const {
    session,
    isAdminAuthenticated,
    isAuthenticating,
    isLoggingOut,
    remainingSeconds,
    retryCooldownSeconds,
    authError,
    logoutNotice,
    lastInvalidationReason,
    loginLocal,
    logout,
    clearAuthFeedback,
  } = useAdminSession();

  // Detectar vista de jugador (para exploración de catálogo público / US3)
  const [currentView, setCurrentView] = useState<"admin" | "player">(() => {
    if (typeof window !== "undefined") {
      const path = window.location.pathname;
      const search = window.location.search;
      const hash = window.location.hash;
      if (path.startsWith("/player") || search.includes("view=player") || hash.startsWith("#/player")) {
        return "player";
      }
    }
    return "admin";
  });

  // Recuerda si hubo una sesión administrativa en el ciclo actual para preservar el árbol
  // montado en caso de expiración temporal (sin exponerlo ni desmontar borradores de F4).
  const [hasEnteredWorkspace, setHasEnteredWorkspace] = useState(false);

  useEffect(() => {
    if (isAdminAuthenticated) {
      setHasEnteredWorkspace(true);
    } else if (lastInvalidationReason === "manual_logout") {
      setHasEnteredWorkspace(false);
    }
  }, [isAdminAuthenticated, lastInvalidationReason]);

  if (currentView === "player") {
    return (
      <div className="min-h-screen bg-arena-bg text-slate-100 flex flex-col">
        <header className="px-4 py-2 bg-slate-900 border-b border-arena-border flex justify-between items-center text-xs">
          <span className="text-slate-400">Modo: Vista Jugador (Catálogo)</span>
          <button
            type="button"
            onClick={() => setCurrentView("admin")}
            className="text-blue-400 hover:text-blue-300 font-medium"
          >
            Ir a Portal Admin →
          </button>
        </header>
        <div className="flex-1">
          <SearchCardsScreen />
        </div>
      </div>
    );
  }

  const preserveWorkspaceInBackground =
    !isAdminAuthenticated &&
    hasEnteredWorkspace &&
    (lastInvalidationReason === "expired" || lastInvalidationReason === "unauthorized_401");

  const workspaceContent = children ?? <CreateCardScreen />;

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100">
      {/* Vista protegida activa únicamente con sesión vigente y rol PLATFORM_ADMIN */}
      {isAdminAuthenticated && session && (
        <AdminLayout
          session={session}
          remainingSeconds={remainingSeconds}
          isLoggingOut={isLoggingOut}
          onLogout={logout}
        >
          <div className="mb-4 flex justify-end">
            <button
              type="button"
              onClick={() => setCurrentView("player")}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              Ver Catálogo Público (Jugador) →
            </button>
          </div>
          {workspaceContent}
        </AdminLayout>
      )}

      {/* Preservación inerte del contenedor de trabajo durante reautenticación por expiración */}
      {preserveWorkspaceInBackground && (
        <div hidden aria-hidden="true" data-testid="preserved-workspace-container">
          {workspaceContent}
        </div>
      )}

      {/* Pantalla de autenticación / reautenticación */}
      {!isAdminAuthenticated && (
        <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12 sm:px-6">
          <div className="w-full max-w-md mb-4 text-right">
            <button
              type="button"
              onClick={() => setCurrentView("player")}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              Ver Catálogo Público (Jugador) →
            </button>
          </div>
          <AdminLoginForm
            isSubmitting={isAuthenticating}
            retryCooldownSeconds={retryCooldownSeconds}
            authError={authError}
            logoutNotice={logoutNotice}
            invalidationReason={lastInvalidationReason}
            onSubmitCredentials={loginLocal}
            onClearFeedback={clearAuthFeedback}
          />
        </div>
      )}
    </div>
  );
}
