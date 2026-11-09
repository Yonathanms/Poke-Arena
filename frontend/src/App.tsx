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
import { SearchCardsScreen } from "./web_player/modules/catalogo/screens/SearchCardsScreen";
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

  // Subpestaña del panel administrativo: "cartas" | "ubicaciones" | "buscador"
  const [adminTab, setAdminTab] = useState<"cartas" | "ubicaciones" | "buscador">("cartas");

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
  //    Exclusivamente portal administrativo (Crear Carta, Crear Ubicación, Buscar Cartas)
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
      <SearchCardsScreen />
    ) : (
      <CreateCardScreen />
    ));

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100">
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
              onClick={() => setAdminTab("cartas")}
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
              onClick={() => setAdminTab("ubicaciones")}
              className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
                adminTab === "ubicaciones"
                  ? "bg-arena-accent text-slate-950 shadow"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Crear Ubicación
            </button>
            <button
              type="button"
              onClick={() => setAdminTab("buscador")}
              className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
                adminTab === "buscador"
                  ? "bg-arena-accent text-slate-950 shadow"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Buscar Cartas
            </button>
          </div>
          <div className="text-xs text-slate-400 font-medium">
            Entorno Administrativo · Poké-Arena
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
