/**
 * Raíz de la aplicación Frontend de Poké-Arena (`shared`, `web_admin` y `web_player`).
 *
 * Flujo de navegación y seguridad:
 * 1. Visitante no autenticado: Presenta exclusivamente la pantalla pública de bienvenida
 *    y login con Google (`WelcomeLoginScreen` en `shared`).
 * 2. Usuario con rol PLAYER: Pasa obligatoriamente por el flujo de onboarding de paquete
 *    inicial (`InitialPackOnboardingScreen` en `web_player/modules/coleccion_inicial`),
 *    gestionando `PENDING_CATALOG`, `READY_TO_OPEN`, `OPENING`, `REVEALED` y avanzando
 *    hacia `VistaPrincipalScreen` al confirmar la apertura (`COMPLETED`).
 * 3. Usuario con rol PLATFORM_ADMIN: Presenta exclusivamente el panel administrativo
 *    (`AdminLayout`) con acceso a Crear Carta, Crear Ubicación y Buscar Cartas, sin
 *    acceso cruzado al perfil de jugador.
 */

import React, { useEffect, useState } from "react";
import { useAdminSession } from "./web_admin/modules/auth/hooks/useAdminSession";
import { WelcomeLoginScreen } from "./shared/components/WelcomeLoginScreen";
import { InitialPackOnboardingScreen } from "./web_player/modules/coleccion_inicial/screens/InitialPackOnboardingScreen";
import { CreateCardScreen } from "./web_admin/modules/catalogo/screens/CreateCardScreen";
import { CreateLocationScreen } from "./web_admin/modules/catalogo/screens/CreateLocationScreen";
import { AdminSearchCardsScreen } from "./web_admin/modules/catalogo/screens/AdminSearchCardsScreen";
import { VistaPrincipalScreen } from "./web_player/modules/vista_principal/screens/VistaPrincipalScreen";
import { AdminLayout } from "./web_admin/shared/AdminLayout";

export interface AppProps {
  readonly children?: React.ReactNode;
}

export default function App({ children }: AppProps = {}): React.ReactElement {
  const {
    session,
    isAuthenticated,
    isAdminAuthenticated,
    isPlayerAuthenticated,
    isLoggingOut,
    remainingSeconds,
    logoutNotice,
    lastInvalidationReason,
    logout,
  } = useAdminSession();

  // Subpestaña del panel administrativo: "cartas" | "ubicaciones" | "buscador" | "jugador"
  const [adminTab, setAdminTab] = useState<"cartas" | "ubicaciones" | "buscador" | "jugador">("cartas");

  // Recuerda si hubo una sesión administrativa en el ciclo actual para preservar borradores
  const [hasEnteredWorkspace, setHasEnteredWorkspace] = useState(false);

  useEffect(() => {
    if (isAdminAuthenticated) {
      setHasEnteredWorkspace(true);
    } else if (lastInvalidationReason === "manual_logout") {
      setHasEnteredWorkspace(false);
    }
  }, [isAdminAuthenticated, lastInvalidationReason]);

  // ---------------------------------------------------------------------------
  // 1. USUARIO NO AUTENTICADO: Pantalla pública en shared con botón de Google
  // ---------------------------------------------------------------------------
  if (!isAuthenticated || !session) {
    return (
      <WelcomeLoginScreen
        onLoginSuccess={() => {
          // El session-store reactivo actualizará automáticamente useAdminSession
        }}
        logoutNotice={logoutNotice}
      />
    );
  }

  // ---------------------------------------------------------------------------
  // 2. USUARIO JUGADOR (PLAYER): Flujo de onboarding y paquete inicial (US 3.1.1)
  //    (READY_TO_OPEN -> OPENING -> REVEALED -> COMPLETED / VistaPrincipalScreen)
  // ---------------------------------------------------------------------------
  if (isPlayerAuthenticated) {
    return (
      <InitialPackOnboardingScreen
        onLogout={logout}
        isLoggingOut={isLoggingOut}
      />
    );
  }

  // ---------------------------------------------------------------------------
  // 3. USUARIO ADMINISTRADOR (PLATFORM_ADMIN):
  //    Panel administrativo con acceso completo a Catálogo y vista de Jugador / Cubos
  // ---------------------------------------------------------------------------
  const preserveWorkspaceInBackground =
    !isAdminAuthenticated &&
    hasEnteredWorkspace &&
    (lastInvalidationReason === "expired" || lastInvalidationReason === "unauthorized_401");

  const workspaceContent =
    children ??
    (adminTab === "ubicaciones" ? (
      <CreateLocationScreen />
    ) : adminTab === "buscador" ? (
      <AdminSearchCardsScreen
        onNavigateToCreate={() => setAdminTab("cartas")}
        onNavigateToPlayerView={() => setAdminTab("jugador")}
      />
    ) : adminTab === "jugador" ? (
      <VistaPrincipalScreen
        onLogout={logout}
        isLoggingOut={isLoggingOut}
      />
    ) : (
      <CreateCardScreen />
    ));

  return (
    <div className="min-h-screen poke-arena-bg text-slate-100">
      <AdminLayout
        session={session}
        remainingSeconds={remainingSeconds}
        isLoggingOut={isLoggingOut}
        onLogout={logout}
      >
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setAdminTab("cartas")}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 ${
                adminTab === "cartas"
                  ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-600/25 border border-blue-400/30"
                  : "bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10"
              }`}
            >
              Crear Carta
            </button>
            <button
              type="button"
              onClick={() => setAdminTab("ubicaciones")}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 ${
                adminTab === "ubicaciones"
                  ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-600/25 border border-blue-400/30"
                  : "bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10"
              }`}
            >
              Crear Ubicación
            </button>
            <button
              type="button"
              onClick={() => setAdminTab("buscador")}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 ${
                adminTab === "buscador"
                  ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-600/25 border border-blue-400/30"
                  : "bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10"
              }`}
            >
              Buscar Cartas
            </button>
            <button
              type="button"
              onClick={() => setAdminTab("jugador")}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 flex items-center gap-1.5 ${
                adminTab === "jugador"
                  ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-600/25 border border-blue-400/30"
                  : "bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10"
              }`}
            >
              <span>Mi Perfil de Jugador</span>
              <span className="px-1.5 py-0.5 rounded-md bg-amber-500/20 border border-amber-500/30 text-amber-300 text-[10px] font-bold">
                Cubos & ELO
              </span>
            </button>
          </div>
        </div>
        {workspaceContent}
      </AdminLayout>

      {/* Preservación inerte del contenedor de trabajo durante reautenticación por expiración */}
      {preserveWorkspaceInBackground && (
        <div hidden aria-hidden="true" data-testid="preserved-workspace-container">
          {workspaceContent}
        </div>
      )}
    </div>
  );
}
