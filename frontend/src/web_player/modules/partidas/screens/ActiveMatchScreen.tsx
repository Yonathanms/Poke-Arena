/** Vista de partida activa (HUD Turno 1, reloj 30 s, apuesta, rival Fog of War, 3 estadios y mano). */

import React from "react";
import { ArrowLeft, Bot, Clock, Coins, Layers, RefreshCw, Skull, User } from "lucide-react";
import pokemonIcon from "../../../../images/icons/icono_pokemon.png";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { LocationBoardSlot } from "../components/LocationBoardSlot";
import { PlayerHandBar } from "../components/PlayerHandBar";
import { useActiveMatch } from "../hooks/useActiveMatch";

export interface ActiveMatchScreenProps {
  readonly matchId: string;
  readonly onBack: () => void;
}

export function ActiveMatchScreen({
  matchId,
  onBack,
}: ActiveMatchScreenProps): React.ReactElement {
  const { match, isLoading, error, secondsRemaining, reload } = useActiveMatch(matchId);

  if (isLoading && !match) {
    return (
      <div className="min-h-screen poke-arena-bg text-slate-100 flex flex-col items-center justify-center p-6">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-300 font-medium">
            Preparando estadios y repartiendo tu mano inicial...
          </p>
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="min-h-screen poke-arena-bg text-slate-100 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-lg flex flex-col gap-4">
          <AlertBanner
            variant="error"
            title={error?.title ?? "No pudimos abrir el duelo"}
            description={
              error?.message ?? "No fue posible cargar el estado actual de la partida."
            }
          />
          <div className="flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => void reload()}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Reintentar</span>
            </button>
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-2 bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Volver a la Arena</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const timerTone =
    secondsRemaining <= 5
      ? "border-red-500/60 bg-red-500/15 text-red-200"
      : secondsRemaining <= 10
        ? "border-amber-400/60 bg-amber-500/15 text-amber-200"
        : "border-blue-400/40 bg-[#090D16]/90 text-white";

  const hiddenCardSlots = Array.from({ length: Math.min(7, match.opponent.hand_count) });

  return (
    <div className="min-h-screen poke-arena-bg text-slate-100 flex flex-col">
      {/* Encabezado HUD compacto */}
      <header className="glass-panel sticky top-0 z-20 px-4 sm:px-6 py-3">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-3">
          {/* Izquierda: Volver y emblema */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-1.5 bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Volver a la Arena</span>
            </button>

            <div className="flex items-center gap-2.5">
              <img src={pokemonIcon} alt="Poké-Arena" className="w-7 h-7 object-contain" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-extrabold text-white">
                    Turno {match.turn_number}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                      match.context === "RANKED"
                        ? "bg-amber-500/15 text-amber-300 border-amber-400/40"
                        : "bg-blue-500/15 text-blue-300 border-blue-400/40"
                    }`}
                  >
                    {match.context === "RANKED" ? "Clasificatoria" : "Torneo"}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">Asiento {match.my_seat}</p>
              </div>
            </div>
          </div>

          {/* Centro: Reloj del turno y apuesta */}
          <div className="flex items-center gap-2.5">
            <div
              className={`rounded-xl border px-3.5 py-1.5 flex items-center gap-2 transition-colors ${timerTone}`}
            >
              <Clock className="w-4 h-4 shrink-0" />
              <span className="font-mono text-base font-extrabold">{secondsRemaining} s</span>
            </div>

            <div className="rounded-xl border border-amber-400/35 bg-[#090D16]/90 px-3.5 py-1.5 flex items-center gap-2">
              <Coins className="w-4 h-4 text-amber-400" />
              <span className="text-xs text-slate-300">Apuesta:</span>
              <span className="text-sm font-extrabold text-amber-400">
                {match.bet_cubes} {match.bet_cubes === 1 ? "Cubo" : "Cubos"}
              </span>
            </div>
          </div>

          {/* Derecha: Rival (Fog of War estricto) */}
          <div className="bg-[#090D16]/90 border border-white/10 rounded-xl px-3.5 py-2 flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center border ${
                  match.opponent.is_bot
                    ? "bg-amber-500/15 border-amber-400/40 text-amber-300"
                    : "bg-blue-500/15 border-blue-400/40 text-blue-300"
                }`}
              >
                {match.opponent.is_bot ? (
                  <Bot className="w-4 h-4" />
                ) : (
                  <User className="w-4 h-4" />
                )}
              </div>
              <div>
                <p className="text-xs font-bold text-white">
                  {match.opponent.is_bot ? "Bot de la Arena" : "Entrenador rival"}
                </p>
                <p className="text-[10px] text-amber-300/90 font-semibold">
                  ELO {match.opponent.elo}
                </p>
              </div>
            </div>

            <div className="h-7 w-px bg-white/10" />

            {/* Reversos ocultos de cartas del rival */}
            <div
              className="flex items-center gap-2"
              title={`El rival tiene ${match.opponent.hand_count} cartas ocultas en mano`}
            >
              <div className="flex -space-x-1.5">
                {hiddenCardSlots.map((_, idx) => (
                  <div
                    key={idx}
                    className="w-4 h-6 rounded-[4px] bg-gradient-to-b from-blue-600/80 to-slate-900 border border-blue-300/40 shadow-sm"
                  />
                ))}
              </div>
              <span className="text-[11px] font-bold text-slate-200">
                {match.opponent.hand_count}
              </span>
            </div>

            <div
              className="flex items-center gap-1 text-[11px] text-slate-300"
              title="Cartas restantes en el mazo del rival"
            >
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-bold">{match.opponent.deck_remaining}</span>
            </div>

            <div
              className="flex items-center gap-1 text-[11px] text-slate-300"
              title="Cartas en el cementerio del rival"
            >
              <Skull className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-bold">{match.opponent.graveyard.length}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Tablero principal */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 flex flex-col justify-between gap-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch">
          {match.locations.map((location, index) => (
            <LocationBoardSlot key={location.id} location={location} index={index} />
          ))}
        </div>

        <PlayerHandBar
          hand={match.my_hand}
          deckRemaining={match.my_deck_remaining}
          graveyardCount={match.my_graveyard.length}
          energy={match.my_energy}
        />
      </main>
    </div>
  );
}
