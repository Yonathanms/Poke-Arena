/** Pantalla principal de la pestaña Arena / Jugar: modo, mazo, cola y reanudación. */

import React, { useEffect, useState } from "react";
import { Coins, Play, Swords, Trophy } from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { DECK_SIZE, type DeckSummary } from "../../decks/types/deck.types";
import { DeckSelectorPanel } from "../components/DeckSelectorPanel";
import { MatchmakingWaitingCard } from "../components/MatchmakingWaitingCard";
import type { UseMatchmakingResult } from "../hooks/useMatchmaking";
import type { MatchContext } from "../types/partidas.types";

const RANKED_MIN_CUBES = 8;
const RANKED_INITIAL_BET = 4;

export interface MatchmakingScreenProps {
  readonly playerCubes: number;
  readonly playerElo: number;
  readonly decks: readonly DeckSummary[];
  readonly decksLoading: boolean;
  readonly matchmaking: UseMatchmakingResult;
  readonly onCreateDeck: () => void;
  readonly onResumeMatch: (matchId: string) => void;
}

export function MatchmakingScreen({
  playerCubes,
  playerElo,
  decks,
  decksLoading,
  matchmaking,
  onCreateDeck,
  onResumeMatch,
}: MatchmakingScreenProps): React.ReactElement {
  const [context, setContext] = useState<MatchContext>("RANKED");
  const [selectedDeckId, setSelectedDeckId] = useState<string | null>(null);

  const validDecks = decks.filter((d) => d.card_count === DECK_SIZE);

  useEffect(() => {
    if (selectedDeckId && validDecks.some((d) => d.id === selectedDeckId)) {
      return;
    }
    setSelectedDeckId(validDecks[0]?.id ?? null);
  }, [validDecks, selectedDeckId]);

  const insufficientCubesForRanked = context === "RANKED" && playerCubes < RANKED_MIN_CUBES;
  const activeDeck = decks.find((d) => d.id === matchmaking.search?.deck_id) ?? null;

  const canSearch =
    Boolean(selectedDeckId) &&
    !insufficientCubesForRanked &&
    !matchmaking.isSubmitting &&
    !matchmaking.activeMatchId;

  return (
    <div className="flex flex-col gap-5">
      {/* Toast breve para avisos no bloqueantes */}
      {matchmaking.notice && (
        <div className="animate-toast-in glass-panel rounded-xl px-4 py-3 border border-blue-400/35 text-xs font-medium text-blue-100 flex items-center justify-between gap-3">
          <span>{matchmaking.notice}</span>
          <button
            type="button"
            onClick={matchmaking.dismissNotice}
            className="text-blue-300 hover:text-white text-xs font-bold shrink-0"
          >
            Entendido
          </button>
        </div>
      )}

      {/* Errores de validación o estado */}
      {matchmaking.error && (
        <AlertBanner
          variant="error"
          title={matchmaking.error.title}
          description={matchmaking.error.message}
          onDismiss={matchmaking.dismissError}
        />
      )}

      {/* Estado de carga inicial */}
      {matchmaking.isInitializing ? (
        <div className="glass-card p-8 flex items-center justify-center gap-3 text-slate-300 text-sm">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span>Comprobando el estado de tu Arena...</span>
        </div>
      ) : matchmaking.activeMatchId ? (
        /* Combate activo detectado */
        <div className="glass-card p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border border-amber-400/35">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/20 border border-amber-400/40 flex items-center justify-center text-amber-300 shrink-0">
              <Swords className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-white">Tienes un combate en curso</h2>
              <p className="text-xs text-slate-300 mt-1">
                Regresa al tablero de la Arena para revisar las ubicaciones y tu mano inicial.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => onResumeMatch(matchmaking.activeMatchId!)}
            className="shrink-0 inline-flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99]"
          >
            <Play className="w-4 h-4" />
            <span>Reanudar duelo</span>
          </button>
        </div>
      ) : matchmaking.search?.status === "SEARCHING" ? (
        /* Búsqueda abierta activa */
        <MatchmakingWaitingCard
          search={matchmaking.search}
          deckName={activeDeck?.name ?? null}
          liveElapsedSeconds={matchmaking.liveElapsedSeconds}
          isCancelling={matchmaking.isCancelling}
          isAcceptingBot={matchmaking.isAcceptingBot}
          onCancel={() => void matchmaking.cancelSearch()}
          onAcceptBot={() => void matchmaking.acceptBot()}
        />
      ) : (
        /* Configuración de búsqueda en reposo */
        <div className="glass-card p-6 sm:p-8 flex flex-col gap-6">
          {/* Cabecera Arena */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-2xl bg-blue-500/15 border border-blue-400/40 flex items-center justify-center text-blue-400 shrink-0">
                <Swords className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-extrabold text-white tracking-tight">
                  Arena de Combate
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Elige el modo de juego y tu mazo de 12 cartas para enfrentar a otro entrenador.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 shrink-0">
              <div className="bg-[#090D16]/90 border border-white/10 rounded-xl px-3.5 py-2 flex items-center gap-2 text-xs">
                <Trophy className="w-4 h-4 text-amber-400" />
                <span className="text-slate-400">ELO:</span>
                <span className="font-extrabold text-amber-400">{playerElo}</span>
              </div>
              <div className="bg-[#090D16]/90 border border-white/10 rounded-xl px-3.5 py-2 flex items-center gap-2 text-xs">
                <Coins className="w-4 h-4 text-amber-400" />
                <span className="text-slate-400">Cubos:</span>
                <span className="font-extrabold text-amber-400">{playerCubes}</span>
              </div>
            </div>
          </div>

          {/* Selector de contexto */}
          <div className="flex flex-col gap-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Modo de partida
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setContext("RANKED")}
                className={`text-left rounded-xl p-4 border transition-all cursor-pointer ${
                  context === "RANKED"
                    ? "bg-blue-500/15 border-blue-500/80 shadow-lg shadow-blue-600/15"
                    : "bg-[#090D16]/90 border-white/10 hover:border-blue-400/40"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-white">Clasificatoria</span>
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-400/40 text-amber-300 text-[10px] font-bold">
                    Apuesta {RANKED_INITIAL_BET} cubos
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Duelo competitivo por ELO y cubos. Requiere un mínimo de {RANKED_MIN_CUBES} cubos
                  disponibles.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setContext("TOURNAMENT")}
                className={`text-left rounded-xl p-4 border transition-all cursor-pointer ${
                  context === "TOURNAMENT"
                    ? "bg-blue-500/15 border-blue-500/80 shadow-lg shadow-blue-600/15"
                    : "bg-[#090D16]/90 border-white/10 hover:border-blue-400/40"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-white">Torneo</span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-400/40 text-emerald-300 text-[10px] font-bold">
                    Sin apuesta de cubos
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Modo de torneo oficial con las mismas reglas de combate y preparación de la
                  Arena.
                </p>
              </button>
            </div>
          </div>

          {/* Advertencia clara si faltan cubos para clasificatoria */}
          {insufficientCubesForRanked && (
            <AlertBanner
              variant="warning"
              title="Saldo insuficiente para Clasificatoria"
              description={`Tienes ${playerCubes} cubos y necesitas al menos ${RANKED_MIN_CUBES} para disputar una partida clasificatoria. Adquiere cubos o elige el modo Torneo para continuar.`}
            />
          )}

          {/* Selector de deck */}
          <DeckSelectorPanel
            decks={decks}
            selectedDeckId={selectedDeckId}
            isLoading={decksLoading}
            disabled={matchmaking.isSubmitting}
            onSelectDeck={setSelectedDeckId}
            onCreateDeck={onCreateDeck}
          />

          {/* Botón buscar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-white/10">
            <p className="text-xs text-slate-400">
              {selectedDeckId
                ? "El mazo quedará bloqueado mientras estés en búsqueda."
                : "Selecciona un mazo completo de 12 cartas para habilitar la búsqueda."}
            </p>
            <button
              type="button"
              disabled={!canSearch}
              onClick={() => {
                if (selectedDeckId) {
                  void matchmaking.startSearch(selectedDeckId, context);
                }
              }}
              className="inline-flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-6 py-2.5 text-sm shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all duration-200 active:scale-[0.99] disabled:opacity-45 disabled:cursor-not-allowed disabled:shadow-none"
            >
              <Swords className="w-4 h-4" />
              <span>{matchmaking.isSubmitting ? "Entrando a la Arena..." : "Buscar Partida"}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
