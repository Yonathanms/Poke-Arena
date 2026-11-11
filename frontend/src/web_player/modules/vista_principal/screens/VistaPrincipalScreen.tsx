/**
 * Pantalla principal del jugador (`web_player/modules/vista_principal`).
 *
 * Responsabilidades:
 * 1. Consultar el perfil persistido en PostgreSQL (`GET /api/v1/identity/me`) mediante `usePlayerProfile`.
 * 2. Mostrar la información del usuario, puntuación ELO, cubos de energía y verificación de conexión a SQL.
 * 3. Proporcionar la acción de cierre de sesión coordinada con el store en memoria.
 * 4. Gestionar los tabs de navegación: Perfil, Catálogo & Colección, Decks.
 */

import React, { useState } from "react";
import { User, BookOpen, Layers } from "lucide-react";
import { ProfileHeader } from "../components/ProfileHeader";
import { PlayerStatsGrid } from "../components/PlayerStatsGrid";
import { DatabaseVerificationCard } from "../components/DatabaseVerificationCard";
import { usePlayerProfile } from "../hooks/usePlayerProfile";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { SearchCardsScreen } from "../../catalogo/screens/SearchCardsScreen";
import { useDecks } from "../../decks/hooks/useDecks";
import { CreateDeckScreen } from "../../decks/screens/CreateDeckScreen";
import { EditDeckScreen } from "../../decks/screens/EditDeckScreen";
import { DecksTabContent } from "../../decks/components/DecksTabContent";

type ActiveTab = "perfil" | "catalogo" | "decks";
type DeckSubView = "list" | "create" | "edit";

export interface VistaPrincipalScreenProps {
  readonly onLogout: () => void;
  readonly isLoggingOut?: boolean;
}

export function VistaPrincipalScreen({
  onLogout,
  isLoggingOut = false,
}: VistaPrincipalScreenProps): React.ReactElement {
  const { profile, isLoading, error, reload } = usePlayerProfile();
  const [activeTab, setActiveTab] = useState<ActiveTab>("perfil");
  const [deckSubView, setDeckSubView] = useState<DeckSubView>("list");
  const [editingDeckId, setEditingDeckId] = useState<string | null>(null);
  const { deckCount, isLoading: decksLoading, reload: reloadDecks } = useDecks();

  // Pantallas full-screen de creación/edición de decks (bypasan el layout de tabs)
  if (deckSubView === "create") {
    return (
      <CreateDeckScreen
        onBack={() => setDeckSubView("list")}
        onSuccess={() => {
          reloadDecks();
          setDeckSubView("list");
          setActiveTab("decks");
        }}
      />
    );
  }

  if (deckSubView === "edit" && editingDeckId) {
    return (
      <EditDeckScreen
        deckId={editingDeckId}
        onBack={() => { setDeckSubView("list"); setEditingDeckId(null); }}
        onSuccess={() => {
          reloadDecks();
          setDeckSubView("list");
          setEditingDeckId(null);
        }}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen poke-arena-bg text-slate-100 flex flex-col items-center justify-center p-6">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-300 font-medium">
            Cargando perfil y estadísticas de entrenador...
          </p>
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="min-h-screen poke-arena-bg text-slate-100 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-lg">
          <AlertBanner
            variant="error"
            title="Error de carga de perfil"
            description={error || "No fue posible recuperar el perfil del jugador en este momento."}
          />
          <div className="mt-4 flex justify-center gap-3">
            <button
              type="button"
              onClick={() => void reload()}
              className="bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl px-5 py-2.5 text-xs shadow-lg shadow-blue-600/25 border border-blue-400/30 transition-all"
            >
              Reintentar
            </button>
            <button
              type="button"
              onClick={onLogout}
              className="bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10 rounded-xl px-4 py-2 text-xs font-semibold transition-all"
            >
              Cerrar Sesión
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen poke-arena-bg text-slate-100 p-4 sm:p-8">
      <div className="max-w-5xl mx-auto flex flex-col gap-6">
        {/* Cabecera con datos de cuenta y logout */}
        <ProfileHeader
          profile={profile}
          onLogout={onLogout}
          isLoggingOut={isLoggingOut}
        />

        {/* Navegación por pestañas */}
        <div className="flex items-center gap-2 border-b border-white/10 pb-3 flex-wrap">
          <button
            type="button"
            onClick={() => setActiveTab("perfil")}
            data-testid="tab-player-profile"
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "perfil"
                ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-600/25 border border-blue-400/30"
                : "bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10"
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
                ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-600/25 border border-blue-400/30"
                : "bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10"
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Catálogo & Mi Colección</span>
            <span className="px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 text-[10px] font-bold">
              Explorar
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("decks")}
            data-testid="tab-player-decks"
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "decks"
                ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-600/25 border border-blue-400/30"
                : "bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 border border-white/10"
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Decks</span>
            {!decksLoading && (
              <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                activeTab === "decks"
                  ? "bg-blue-950/60 text-blue-200 border border-blue-300/40"
                  : "bg-slate-700 text-slate-300"
              }`}>
                {deckCount}
              </span>
            )}
          </button>
        </div>

        {/* Vista activa según la pestaña seleccionada */}
        {activeTab === "perfil" ? (
          <div className="flex flex-col gap-6 animate-fade-in">
            <PlayerStatsGrid profile={profile} />
            <DatabaseVerificationCard profile={profile} deckCount={deckCount} />
          </div>
        ) : activeTab === "catalogo" ? (
          <div className="animate-fade-in">
            <SearchCardsScreen mode="player" />
          </div>
        ) : (
          <div className="animate-fade-in">
            <DecksTabContent
              onCreateDeck={() => setDeckSubView("create")}
              onEditDeck={(deckId) => { setEditingDeckId(deckId); setDeckSubView("edit"); }}
              onDecksChanged={reloadDecks}
            />
          </div>
        )}
      </div>
    </div>
  );
}
