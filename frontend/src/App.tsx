import React, { useCallback, useEffect, useState } from "react";
import { Navbar } from "./shared/components/Navbar";
import { CardList } from "./modules/content/components/CardList";
import { CreateCardForm } from "./modules/content/components/CreateCardForm";
import { LocationList } from "./modules/content/components/LocationList";
import { CreateLocationForm } from "./modules/content/components/CreateLocationForm";
import { apiFetch } from "./shared/api/client";
import {
  clearPlatformAccessToken,
  PLATFORM_SESSION_INVALIDATED_EVENT,
} from "./shared/auth/session";
import { PlatformSessionDTO } from "./modules/identity/api/identity";
import { disableGoogleAutoSelect } from "./modules/identity/components/GoogleSignInButton";

interface FrontendPlatformSession {
  userId: string;
  role: PlatformSessionDTO["role"];
  expiresAt: number;
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    "catalog" | "create-card" | "create-location" | "locations"
  >("catalog");
  const [session, setSession] = useState<FrontendPlatformSession | null>(null);
  const [authMessage, setAuthMessage] = useState<string | null>(null);

  const handleAuthenticated = useCallback((platformSession: PlatformSessionDTO): void => {
    setSession({
      userId: platformSession.user_id,
      role: platformSession.role,
      expiresAt: Date.now() + platformSession.expires_in * 1000,
    });
    setAuthMessage(null);
  }, []);

  const clearSession = useCallback((): void => {
    clearPlatformAccessToken();
    disableGoogleAutoSelect();
    setSession(null);
  }, []);

  const handleLogout = useCallback(async (): Promise<void> => {
    try {
      await apiFetch<void>("/identity/session", { method: "DELETE" });
      setAuthMessage("La sesión se cerró correctamente.");
    } catch {
      setAuthMessage(
        "Se cerró la sesión en este navegador; no se pudo confirmar la revocación en el servidor."
      );
    } finally {
      clearSession();
    }
  }, [clearSession]);

  useEffect(() => {
    const handleSessionInvalidated = (): void => {
      setSession(null);
      setAuthMessage("La sesión dejó de ser válida. Inicia sesión nuevamente para continuar.");
    };
    window.addEventListener(PLATFORM_SESSION_INVALIDATED_EVENT, handleSessionInvalidated);
    return () =>
      window.removeEventListener(PLATFORM_SESSION_INVALIDATED_EVENT, handleSessionInvalidated);
  }, []);

  useEffect(() => {
    if (!session) return;
    const expiresInMs = Math.max(0, session.expiresAt - Date.now());
    const timer = window.setTimeout(() => {
      clearSession();
      setAuthMessage("La sesión expiró. Inicia sesión nuevamente para continuar.");
    }, expiresInMs);
    return () => window.clearTimeout(timer);
  }, [session, clearSession]);

  return (
    <div className="min-h-screen flex flex-col bg-arena-bg text-slate-100">
      {/* Navbar con estado del sistema */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        session={session}
        onAuthenticated={handleAuthenticated}
        onLogout={() => void handleLogout()}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {authMessage && (
          <div
            role="status"
            className="mb-5 rounded-xl border border-blue-500/30 bg-blue-500/10 p-3 text-sm text-blue-100"
          >
            {authMessage}
          </div>
        )}
        {activeTab === "catalog" && <CardList isAuthenticated={!!session} />}
        {activeTab === "create-card" && !session && (
          <section className="glass-panel rounded-2xl border border-amber-500/30 p-8 text-center">
            <h2 className="text-lg font-semibold text-slate-100">Inicia sesión para crear cartas</h2>
            <p className="mt-2 text-sm text-slate-300">
              Usa el botón de Google en la barra superior. Se requiere una cuenta autorizada como administradora.
            </p>
          </section>
        )}
        {activeTab === "create-card" && session && session.role !== "PLATFORM_ADMIN" && (
          <section className="glass-panel rounded-2xl border border-red-500/30 p-8 text-center">
            <h2 className="text-lg font-semibold text-slate-100">Permiso de administrador requerido</h2>
            <p className="mt-2 text-sm text-slate-300">
              La cuenta autenticada no tiene permiso para crear cartas.
            </p>
          </section>
        )}
        {activeTab === "create-card" && session?.role === "PLATFORM_ADMIN" && (
          <CreateCardForm onSuccess={() => setActiveTab("catalog")} />
        )}
        {activeTab === "locations" && <LocationList />}
        {activeTab === "create-location" && !session && (
          <section className="glass-panel rounded-2xl border border-amber-500/30 p-8 text-center">
            <h2 className="text-lg font-semibold text-slate-100">Inicia sesión para crear ubicaciones</h2>
            <p className="mt-2 text-sm text-slate-300">
              Usa el botón de Google en la barra superior. Se requiere una cuenta autorizada como administradora.
            </p>
          </section>
        )}
        {activeTab === "create-location" && session && session.role !== "PLATFORM_ADMIN" && (
          <section className="glass-panel rounded-2xl border border-red-500/30 p-8 text-center">
            <h2 className="text-lg font-semibold text-slate-100">Permiso de administrador requerido</h2>
            <p className="mt-2 text-sm text-slate-300">
              La cuenta autenticada no tiene permiso para crear ubicaciones.
            </p>
          </section>
        )}
        {activeTab === "create-location" && session?.role === "PLATFORM_ADMIN" && (
          <CreateLocationForm onSuccess={() => setActiveTab("locations")} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-arena-border/60 py-6 mt-12 bg-arena-card/30">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-500 space-y-1">
          <p>
            <strong className="text-slate-400">Poké-Arena</strong> — Plataforma Web de Cartas Coleccionables • Equipo MAFY
          </p>
          <p>
            Sprint 1: Crear Carta (F-02, 5:7) • Crear Ubicación (F-03, 4:3) • Buscar Carta (US 2.1.2 MongoDB)
          </p>
        </div>
      </footer>
    </div>
  );
};

export default App;
