/** Tarjeta de espera en cola con radar animado, bloqueo de mazo y oferta de Bot tras 60 s. */

import React from "react";
import { Bot, Clock, Lock, Shield, Trophy, XCircle } from "lucide-react";
import pokemonIcon from "../../../../images/icons/icono_pokemon.png";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import {
  formatElapsedClock,
  type MatchSearchDTO,
} from "../types/partidas.types";

export interface MatchmakingWaitingCardProps {
  readonly search: MatchSearchDTO;
  readonly deckName: string | null;
  readonly liveElapsedSeconds: number;
  readonly isCancelling: boolean;
  readonly isAcceptingBot: boolean;
  readonly onCancel: () => void;
  readonly onAcceptBot: () => void;
}

export function MatchmakingWaitingCard({
  search,
  deckName,
  liveElapsedSeconds,
  isCancelling,
  isAcceptingBot,
  onCancel,
  onAcceptBot,
}: MatchmakingWaitingCardProps): React.ReactElement {
  const isRanked = search.context === "RANKED";
  const botAvailable = search.bot_offer_available;
  const botRemaining = Math.max(0, 60 - liveElapsedSeconds);
  const showInsufficientLocations = search.warning_code === "ubicaciones_insuficientes";

  return (
    <div className="glass-card p-6 sm:p-8 flex flex-col gap-6">
      {/* Encabezado de radar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5">
        <div className="flex items-center gap-4">
          <div className="relative w-16 h-16 flex items-center justify-center shrink-0">
            <span className="absolute inset-0 rounded-full bg-blue-500/25 animate-ping" />
            <span className="absolute inset-1 rounded-full border border-blue-400/50" />
            <div className="relative w-14 h-14 rounded-full bg-[#090D16]/90 border border-blue-400/40 flex items-center justify-center shadow-lg shadow-blue-600/25">
              <img
                src={pokemonIcon}
                alt="Radar de la Arena"
                className="w-9 h-9 object-contain"
              />
            </div>
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-extrabold text-white tracking-tight">
                Buscando rival en la Arena...
              </h2>
              <span
                className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                  isRanked
                    ? "bg-amber-500/15 text-amber-300 border-amber-400/40"
                    : "bg-blue-500/15 text-blue-300 border-blue-400/40"
                }`}
              >
                {isRanked ? "Clasificatoria" : "Torneo"}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Emparejando entrenadores de nivel cercano. La búsqueda se amplía automáticamente con
              el tiempo.
            </p>
          </div>
        </div>

        {/* Cronómetro y ELO */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="bg-[#090D16]/90 border border-white/10 rounded-xl px-4 py-2.5 text-center">
            <div className="flex items-center justify-center gap-1.5 text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
              <Clock className="w-3.5 h-3.5 text-blue-400" />
              <span>Tiempo</span>
            </div>
            <p className="text-lg font-extrabold font-mono text-white mt-0.5">
              {formatElapsedClock(liveElapsedSeconds)}
            </p>
          </div>

          <div className="bg-[#090D16]/90 border border-amber-500/25 rounded-xl px-4 py-2.5 text-center">
            <div className="flex items-center justify-center gap-1.5 text-[11px] text-amber-300/80 font-semibold uppercase tracking-wider">
              <Trophy className="w-3.5 h-3.5 text-amber-400" />
              <span>ELO</span>
            </div>
            <p className="text-lg font-extrabold text-amber-400 mt-0.5">
              {search.elo_snapshot}
            </p>
          </div>
        </div>
      </div>

      {/* Aviso diegético si faltan estadios jugables */}
      {showInsufficientLocations && (
        <AlertBanner
          variant="warning"
          title="Estadios en preparación"
          description="Encontramos un rival compatible, pero aún no hay suficientes estadios habilitados en la Arena. Sigues en espera sin perder tu turno."
        />
      )}

      {/* Resumen de mazo bloqueado */}
      <div className="bg-[#090D16]/90 border border-white/10 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-slate-800/80 border border-white/10 flex items-center justify-center text-amber-400 shrink-0">
            <Lock className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-white truncate">
              {deckName ?? "Mazo seleccionado"}
            </p>
            <p className="text-xs text-slate-400">
              Mazo bloqueado durante la búsqueda. Cancela la búsqueda si deseas cambiar de mazo.
            </p>
          </div>
        </div>

        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-400/40 text-emerald-300 text-[11px] font-bold shrink-0">
          <Shield className="w-3.5 h-3.5" />
          <span>En cola</span>
        </span>
      </div>

      {/* Oferta del Bot a los 60 s o cuenta regresiva */}
      {botAvailable ? (
        <div className="rounded-2xl border border-amber-400/40 bg-amber-500/10 p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-xl bg-amber-500/20 border border-amber-400/40 flex items-center justify-center text-amber-300 shrink-0">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-amber-200">
                ¿Sin rival aún? Puedes desafiar al Bot de la Arena o seguir esperando
              </h3>
              <p className="text-xs text-amber-100/80 mt-1">
                El duelo contra el Bot usa tu mazo bloqueado y exactamente las mismas reglas de la
                Arena. Si decides seguir esperando rival humano, esta opción seguirá disponible.
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={isAcceptingBot || isCancelling}
            onClick={onAcceptBot}
            className="shrink-0 inline-flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99] disabled:opacity-50"
          >
            <Bot className="w-4 h-4" />
            <span>{isAcceptingBot ? "Preparando Arena..." : "Jugar contra el Bot"}</span>
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2 text-xs text-slate-400 px-1">
          <span className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-slate-500" />
            <span>Si no aparece un entrenador rival, podrás enfrentar al Bot de la Arena.</span>
          </span>
          <span className="font-mono font-bold text-slate-300 shrink-0">
            Disponible en {botRemaining} s
          </span>
        </div>
      )}

      {/* Acción de cancelar */}
      <div className="flex justify-end pt-1 border-t border-white/10">
        <button
          type="button"
          disabled={isCancelling || isAcceptingBot}
          onClick={onCancel}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 text-red-200 rounded-xl transition-all disabled:opacity-50"
        >
          <XCircle className="w-4 h-4" />
          <span>{isCancelling ? "Cancelando..." : "Cancelar búsqueda"}</span>
        </button>
      </div>
    </div>
  );
}
