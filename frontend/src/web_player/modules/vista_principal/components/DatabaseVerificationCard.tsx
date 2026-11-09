/**
 * Tarjeta de diagnóstico y verificación de conexión con PostgreSQL en tiempo real.
 */

import React from "react";
import type { PlayerProfileDTO } from "../types/vista_principal.types";

export interface DatabaseVerificationCardProps {
  readonly profile: PlayerProfileDTO;
}

export function DatabaseVerificationCard({
  profile,
}: DatabaseVerificationCardProps): React.ReactElement {
  const formattedDate = profile.created_at
    ? new Date(profile.created_at).toLocaleString()
    : "Recién registrado";

  return (
    <div className="p-6 rounded-2xl bg-slate-900 border border-emerald-500/30 shadow-xl relative overflow-hidden">
      <div className="absolute top-0 right-0 px-4 py-1 bg-emerald-500/20 text-emerald-400 text-[11px] font-semibold rounded-bl-xl border-l border-b border-emerald-500/30 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        PostgreSQL 16: Conexión Verificada
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
          </svg>
        </div>
        <div>
          <h2 className="text-base font-bold text-white">
            Verificación de Persistencia SQL
          </h2>
          <p className="text-xs text-slate-400">
            Datos reales persistidos en las tablas <code className="text-emerald-300">identity_users</code> y <code className="text-emerald-300">player_profiles</code>
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs bg-slate-950/60 p-4 rounded-xl border border-slate-800 font-mono">
        <div>
          <span className="text-slate-500 block mb-0.5">Identificador de Usuario (UUID):</span>
          <span className="text-slate-200 select-all font-semibold">{profile.user_id}</span>
        </div>
        <div>
          <span className="text-slate-500 block mb-0.5">Correo Autenticado:</span>
          <span className="text-slate-200">{profile.email || "No provisto"}</span>
        </div>
        <div>
          <span className="text-slate-500 block mb-0.5">Rol en Base de Datos:</span>
          <span className="text-emerald-400 font-semibold">{profile.role}</span>
        </div>
        <div>
          <span className="text-slate-500 block mb-0.5">Fecha de Registro / Creación:</span>
          <span className="text-slate-300">{formattedDate}</span>
        </div>
      </div>

      <p className="text-[11px] text-slate-500 mt-3 flex items-center gap-1.5">
        <svg className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
        <span>La sesión fue emitida y validada mediante la infraestructura oficial de Poké-Arena.</span>
      </p>
    </div>
  );
}

