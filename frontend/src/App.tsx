/**
 * Raíz de la aplicación Frontend de Poké-Arena (`web_admin` y `web_player`).
 *
 * Responsabilidades:
 * 1. Coordinar el ciclo de autenticación administrativa a través de `useAdminSession`.
 * 2. Restringir el acceso a `AdminLayout`, `CreateCardScreen` y `CreateLocationScreen`
 *    exclusivamente cuando existe una sesión activa con rol `PLATFORM_ADMIN`.
 * 3. Si una sesión expira o se invalida por `401` después de que el administrador ya
 *    había ingresado al área de trabajo, mantener el árbol del área de trabajo montado
 *    en memoria (oculto e inerte con `hidden` / `aria-hidden`) mientras presenta el
 *    formulario de reautenticación, preservando el borrador y cualquier `Idempotency-Key`
 *    pendiente sin exponer contenido protegido ni usar `localStorage`.
 * 4. Permitir la visualización del catálogo de jugadores (`SearchCardsScreen`) mediante
 *    el selector de vista o ruta de jugador (`?view=player` o `/player`).
 * 5. Permitir la navegación rápida y acceso a creación de ubicaciones (`CreateLocationScreen`)
 *    tanto desde la pestaña del portal administrativo como mediante la ruta hash `#/ubicaciones`.
 */

import React, { useEffect, useState } from "react";
import { AdminLoginForm } from "./web_admin/modules/auth/components/AdminLoginForm";
import { useAdminSession } from "./web_admin/modules/auth/hooks/useAdminSession";
import { CreateCardScreen } from "./web_admin/modules/catalogo/screens/CreateCardScreen";
import { CreateLocationScreen } from "./web_admin/modules/catalogo/screens/CreateLocationScreen";
import { SearchCardsScreen } from "./web_player/modules/catalogo/screens/SearchCardsScreen";
import { AdminLayout } from "./web_admin/shared/AdminLayout";

export interface AppProps {
  readonly children?: React.ReactNode;
}

export default function App({ children }: AppProps = {}): React.ReactElement {
  const [currentHash, setCurrentHash] = useState(() =>
    typeof window !== "undefined" ? window.location.hash : ""
  );

  useEffect(() => {
    const handleHashChange = () => setCurrentHash(window.location.hash);
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

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

  // Subpestaña del panel administrativo: "cartas" | "ubicaciones"
  const [adminTab, setAdminTab] = useState<"cartas" | "ubicaciones">(() => {
    if (typeof window !== "undefined" && window.location.hash === "#/ubicaciones") {
      return "ubicaciones";
    }
    return "cartas";
  });

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

  // Acceso directo a la pantalla de ubicación vía hash (cuando no autenticado)
  if (currentHash === "#/ubicaciones" && !isAdminAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <header className="px-4 py-2 bg-slate-900 border-b border-arena-border flex justify-between items-center text-xs">
          <span className="text-slate-400">Modo Directo: Crear Ubicación</span>
          <button
            type="button"
            onClick={() => {
              window.location.hash = "";
              setCurrentHash("");
            }}
            className="text-blue-400 hover:text-blue-300 font-medium"
          >
            ← Volver a Inicio
          </button>
        </header>
        <div className="flex-1">
          <CreateLocationScreen />
        </div>
      </div>
    );
  }

  const preserveWorkspaceInBackground =
    !isAdminAuthenticated &&
    hasEnteredWorkspace &&
    (lastInvalidationReason === "expired" || lastInvalidationReason === "unauthorized_401");

  const workspaceContent =
    children ?? (adminTab === "ubicaciones" ? <CreateLocationScreen /> : <CreateCardScreen />);

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
          <div className="mb-4 flex items-center justify-between border-b border-arena-border pb-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setAdminTab("cartas");
                  if (window.location.hash === "#/ubicaciones") {
                    window.location.hash = "";
                  }
                }}
                className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
                  adminTab === "cartas"
                    ? "bg-arena-accent text-slate-950 shadow"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                Crear Carta
              </button>
              <button
                type="button"
                onClick={() => {
                  setAdminTab("ubicaciones");
                  window.location.hash = "#/ubicaciones";
                }}
                className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
                  adminTab === "ubicaciones"
                    ? "bg-arena-accent text-slate-950 shadow"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                Crear Ubicación
              </button>
            </div>
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
          <div className="w-full max-w-md mb-4 flex justify-between text-xs">
            <a
              href="#/ubicaciones"
              onClick={() => setCurrentHash("#/ubicaciones")}
              className="text-blue-400 hover:text-blue-300 transition-colors"
            >
              Crear Ubicación →
            </a>
            <button
              type="button"
              onClick={() => setCurrentView("player")}
              className="text-blue-400 hover:text-blue-300 transition-colors"
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
