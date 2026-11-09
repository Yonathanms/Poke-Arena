/**
 * Cabecera con datos de identidad del usuario y botón de logout.
 */

import React from "react";
import type { PlayerProfileDTO } from "../types/vista_principal.types";

export interface ProfileHeaderProps {
  readonly profile: PlayerProfileDTO;
  readonly onLogout: () => void;
  readonly isLoggingOut?: boolean;
}

export function ProfileHeader({
  profile,
  onLogout,
  isLoggingOut = false,
}: ProfileHeaderProps): React.ReactElement {
  const roleName = profile.role === "PLATFORM_ADMIN" ? "Administrador de Plataforma" : "Jugador Oficial";
  const roleColor = profile.role === "PLATFORM_ADMIN" ? "bg-amber-500/20 text-amber-300 border-amber-500/30" : "bg-blue-500/20 text-blue-300 border-blue-500/30";

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-slate-900 border border-arena-border shadow-xl">
      <div className="flex items-center gap-4">
        {/* Avatar o Inicial */}
        <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-500/20 border border-blue-400/30">
          {profile.email ? profile.email.charAt(0).toUpperCase() : "P"}
        </div>
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white">
              {profile.email || "Usuario de Poké-Arena"}
            </h1>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${roleColor}`}>
              {roleName}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Sesión activa verificada mediante Google OIDC y PostgreSQL
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onLogout}
          disabled={isLoggingOut}
          className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 hover:text-white border border-slate-700 transition-colors disabled:opacity-50"
        >
          {isLoggingOut ? "Cerrando sesión..." : "Cerrar Sesión"}
        </button>
      </div>
    </div>
  );
}

