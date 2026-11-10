/**
 * Pantalla principal del jugador (`web_player/modules/vista_principal`).
 *
 * Responsabilidades:
 * 1. Consultar el perfil persistido en PostgreSQL (`GET /api/v1/identity/me`) mediante `usePlayerProfile`.
 * 2. Mostrar la información del usuario, puntuación ELO, cubos de energía y verificación de conexión a SQL.
 * 3. Proporcionar la acción de cierre de sesión coordinada con el store en memoria.
 */

import React, { useState } from "react";
import { User, BookOpen } from "lucide-react";
import { ProfileHeader } from "../components/ProfileHeader";
import { PlayerStatsGrid } from "../components/PlayerStatsGrid";
import { DatabaseVerificationCard } from "../components/DatabaseVerificationCard";
import { usePlayerProfile } from "../hooks/usePlayerProfile";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { SearchCardsScreen } from "../../catalogo/screens/SearchCardsScreen";

export interface VistaPrincipalScreenProps {
  readonly onLogout: () => void;
  readonly isLoggingOut?: boolean;
}

export function VistaPrincipalScreen({
  onLogout,
  isLoggingOut = false,
}: VistaPrincipalScreenProps): React.ReactElement {
  const { profile, isLoading, error, reload } = usePlayerProfile();
  const [activeTab, setActiveTab] = useState<"perfil" | "catalogo">("perfil");

  if (isLoading) {
    return (
      <div className="min-h-screen bg-arena-bg text-slate-100 flex flex-col items-center justify-center p-6">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-400 font-medium">
            Consultando perfil y estadísticas en PostgreSQL...
          </p>
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="min-h-screen bg-arena-bg text-slate-100 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-lg">
          <AlertBanner
            variant="error"
            title="Error de carga de perfil"
            description={error || "No fue posible recuperar el perfil del jugador desde PostgreSQL."}
          />
          <div className="mt-4 flex justify-center gap-3">
            <button
              type="button"
              onClick={() => void reload()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold"
            >
              Reintentar
            </button>
            <button
              type="button"
              onClick={onLogout}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
            >
              Cerrar Sesión
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100 p-4 sm:p-8">
      <div className="max-w-5xl mx-auto flex flex-col gap-6">
        {/* Cabecera con datos de cuenta y logout */}
        <ProfileHeader
          profile={profile}
          onLogout={onLogout}
          isLoggingOut={isLoggingOut}
        />

        {/* Navegación por pestañas del Jugador: Perfil vs Catálogo & Colección */}
        <div className="flex items-center gap-2 border-b border-arena-border/60 pb-3">
          <button
            type="button"
            onClick={() => setActiveTab("perfil")}
            data-testid="tab-player-profile"
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "perfil"
                ? "bg-blue-600 text-white shadow-lg shadow-blue-500/20"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-700"
            }`}
          >
            <User className="w-4 h-4" />
            <span>Mi Perfil & Estadísticas</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("catalogo")}
            data-testid="tab-player-catalog"
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "catalogo"
                ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-700"
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Catálogo & Mi Colección</span>
            <span className="px-1.5 py-0.5 rounded-full bg-emerald-950/60 text-emerald-300 border border-emerald-400/40 text-[10px] font-bold">
              Explorar
            </span>
          </button>
        </div>

        {/* Vista activa según la pestaña seleccionada */}
        {activeTab === "perfil" ? (
          <div className="flex flex-col gap-6 animate-fade-in">
            {/* Cuadrícula de estadísticas de juego */}
            <PlayerStatsGrid profile={profile} />

            {/* Tarjeta de verificación técnica contra PostgreSQL */}
            <DatabaseVerificationCard profile={profile} />
          </div>
        ) : (
          <div className="animate-fade-in">
            <SearchCardsScreen mode="player" />
          </div>
        )}
      </div>
    </div>
  );
}
