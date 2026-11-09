/**
 * Raíz de la aplicación Frontend de Poké-Arena (`shared`, `web_admin` y `web_player`).
 *
 * Flujo de navegación y seguridad:
 * 1. Visitante no autenticado: Presenta exclusivamente la pantalla pública de bienvenida
 *    y login con Google (`WelcomeLoginScreen` en `shared`).
 * 2. Usuario con rol PLAYER: Presenta la vista principal del jugador (`VistaPrincipalScreen` en
 *    `web_player/modules/vista_principal`), mostrando estadísticas, balance de cubos y confirmación SQL.
 * 3. Usuario con rol PLATFORM_ADMIN: Presenta el panel administrativo (`AdminLayout`) permitiendo
 *    crear cartas, ubicaciones o alternar hacia la vista de jugador.
 */

import React, { useEffect, useState } from "react";
import { useAdminSession } from "./web_admin/modules/auth/hooks/useAdminSession";
import { WelcomeLoginScreen } from "./shared/components/WelcomeLoginScreen";
import { VistaPrincipalScreen } from "./web_player/modules/vista_principal/screens/VistaPrincipalScreen";
import { CreateCardScreen } from "./web_admin/modules/catalogo/screens/CreateCardScreen";
import { CreateLocationScreen } from "./web_admin/modules/catalogo/screens/CreateLocationScreen";
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

  // Subpestaña del panel administrativo: "cartas" | "ubicaciones"
  const [adminTab, setAdminTab] = useState<"cartas" | "ubicaciones">("cartas");

  // Vista activa para administradores: "admin" (gestión) | "player" (su perfil/vista de jugador)
  const [activeAdminMode, setActiveAdminMode] = useState<"admin" | "player">("admin");

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
  // 2. USUARIO JUGADOR (PLAYER): Vista principal modularizada del jugador
  // ---------------------------------------------------------------------------
  if (isPlayerAuthenticated) {
    return (
      <VistaPrincipalScreen
        onLogout={logout}
        isLoggingOut={isLoggingOut}
      />
    );
  }

  // ---------------------------------------------------------------------------
  // 3. USUARIO ADMINISTRADOR (PLATFORM_ADMIN):
  //    Puede alternar entre la vista administrativa y la vista de jugador
  // ---------------------------------------------------------------------------
  if (activeAdminMode === "player") {
    return (
      <div className="min-h-screen bg-arena-bg text-slate-100 flex flex-col">
        <header className="px-6 py-2.5 bg-slate-900 border-b border-arena-border flex justify-between items-center text-xs">
          <span className="text-amber-400 font-medium flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            Modo Administrador visualizando Vista de Jugador
          </span>
          <button
            type="button"
            onClick={() => setActiveAdminMode("admin")}
            className="px-3 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors"
          >
            ← Volver al Panel Admin
          </button>
        </header>
        <div className="flex-1">
          <VistaPrincipalScreen
            onLogout={logout}
            isLoggingOut={isLoggingOut}
          />
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
          </div>
          <button
            type="button"
            onClick={() => setActiveAdminMode("player")}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1 font-medium"
          >
            Ver Mi Perfil de Jugador →
          </button>
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
