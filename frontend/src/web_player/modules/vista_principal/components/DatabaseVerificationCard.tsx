/**
 * Ficha Oficial de Entrenador (Trainer Card) en el perfil principal del jugador.
 */

import React from "react";
import { Award, BookOpen, Layers, ShieldCheck } from "lucide-react";
import type { PlayerProfileDTO } from "../types/vista_principal.types";

export interface DatabaseVerificationCardProps {
  readonly profile: PlayerProfileDTO;
  readonly deckCount?: number;
}

function getCompetitiveRankTitle(elo: number): string {
  if (elo >= 1800) return "Maestro de la Arena";
  if (elo >= 1400) return "Veterano de Élite";
  if (elo >= 1000) return "Contendiente Oficial";
  return "Aspirante de la Liga";
}

export function DatabaseVerificationCard({
  profile,
  deckCount = 0,
}: DatabaseVerificationCardProps): React.ReactElement {
  const formattedDate = profile.created_at
    ? new Date(profile.created_at).toLocaleDateString("es-ES", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "Temporada actual";

  const rankTitle = getCompetitiveRankTitle(profile.elo);

  return (
    <div className="p-6 glass-card relative overflow-hidden">
      <div className="absolute top-0 right-0 px-4 py-1.5 bg-amber-500/15 text-amber-300 text-[11px] font-bold rounded-bl-xl border-l border-b border-amber-500/30 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        Licencia Oficial Activa
      </div>

      <div className="flex items-center gap-3.5 mb-5">
        <div className="p-2.5 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-400">
          <Award className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">
            Ficha Oficial de Entrenador
          </h2>
          <p className="text-xs text-slate-400">
            Resumen competitivo y estado de progresión en Poké-Arena
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        {/* 1. Rango Competitivo */}
        <div className="bg-[#090D16]/85 p-4 rounded-xl border border-white/10 space-y-1.5">
          <div className="flex items-center gap-2 text-amber-400 font-semibold">
            <Award className="w-4 h-4 shrink-0" />
            <span className="uppercase tracking-wider text-[11px]">Rango Competitivo</span>
          </div>
          <p className="text-sm font-bold text-white">{rankTitle}</p>
          <p className="text-[11px] text-slate-400">
            Clasificación actual con <span className="text-amber-300 font-semibold">{profile.elo} PTS</span>
          </p>
        </div>

        {/* 2. Progreso de Colección */}
        <div className="bg-[#090D16]/85 p-4 rounded-xl border border-white/10 space-y-1.5">
          <div className="flex items-center gap-2 text-blue-400 font-semibold">
            <BookOpen className="w-4 h-4 shrink-0" />
            <span className="uppercase tracking-wider text-[11px]">Progreso de Colección</span>
          </div>
          <p className="text-sm font-bold text-white">
            {profile.has_received_initial_collection
              ? "Colección Inicial Desbloqueada"
              : "Paquete Inicial Disponible"}
          </p>
          <p className="text-[11px] text-slate-400">
            Cartas listas para personalizar tus estrategias
          </p>
        </div>

        {/* 3. Estado de Mazos */}
        <div className="bg-[#090D16]/85 p-4 rounded-xl border border-white/10 space-y-1.5">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold">
            <Layers className="w-4 h-4 shrink-0" />
            <span className="uppercase tracking-wider text-[11px]">Estado de Mazos</span>
          </div>
          <p className="text-sm font-bold text-white">
            {deckCount > 0
              ? `${deckCount} ${deckCount === 1 ? "Mazo Listo" : "Mazos Listos"} para la Arena`
              : "Sin mazos armados aún"}
          </p>
          <p className="text-[11px] text-slate-400">
            Miembro desde {formattedDate}
          </p>
        </div>
      </div>

      <p className="text-[11px] text-slate-400 mt-4 flex items-center gap-1.5">
        <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
        <span>Credencial de entrenador habilitada para torneos y duelos oficiales en Poké-Arena.</span>
      </p>
    </div>
  );
}

