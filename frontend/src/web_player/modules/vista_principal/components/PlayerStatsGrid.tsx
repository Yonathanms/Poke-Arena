/** Cuadrícula de estadísticas del jugador (ELO, Cubos, Colección Inicial). */

import React from "react";
import type { PlayerProfileDTO } from "../types/vista_principal.types";

export interface PlayerStatsGridProps {
  readonly profile: PlayerProfileDTO;
}

export function PlayerStatsGrid({ profile }: PlayerStatsGridProps): React.ReactElement {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {/* Tarjeta ELO */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-arena-border shadow-lg">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Rating ELO</span>
          <span className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </span>
        </div>
        <div className="text-2xl font-extrabold text-white">
          {profile.elo} <span className="text-sm font-normal text-slate-400">PTS</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">Puntuación inicial competitiva</p>
      </div>

      {/* Tarjeta Cubos de Energía */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-arena-border shadow-lg">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Cubos de Energía</span>
          <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </span>
        </div>
        <div className="text-2xl font-extrabold text-white">
          {profile.cubes} <span className="text-sm font-normal text-slate-400">Cubos</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1">Saldo verificado en PostgreSQL</p>
      </div>

      {/* Tarjeta Colección Inicial */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-arena-border shadow-lg">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Colección Inicial</span>
          <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </span>
        </div>
        <div className="text-lg font-bold text-slate-200">
          {profile.has_received_initial_collection ? (
            <span className="text-emerald-400">Entregada ✓</span>
          ) : (
            <span className="text-amber-400">Pendiente</span>
          )}
        </div>
        <p className="text-[11px] text-slate-500 mt-1">Paquete de bienvenida de 12 cartas</p>
      </div>

    </div>
  );
}

