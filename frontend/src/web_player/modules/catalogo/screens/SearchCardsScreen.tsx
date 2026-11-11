import React, { useState } from 'react';
import { useCardSearch } from '../hooks/useCardSearch';
import { SearchBar, CardGrid, EmptyState, CardDetailModal } from '../components/search_page';
import { PokemonCard } from '../types/card.types';
import { RefreshCw, AlertTriangle, Layers, BookOpen } from 'lucide-react';

export interface SearchCardsScreenProps {
  readonly mode?: 'player' | 'admin';
}

export const SearchCardsScreen: React.FC<SearchCardsScreenProps> = ({ mode = 'player' }) => {
  const {
    searchQuery,
    setSearchQuery,
    hasSearched,
    isLoading,
    error,
    isCatalogUnavailable,
    results,
    totalResults,
    currentPage,
    totalPages,
    handleSearch,
    handleClear,
    goToPage,
    nextPage,
    prevPage,
    reload,
    selectedType,
    setSelectedType,
    selectedRarity,
    setSelectedRarity,
    selectedCost,
    setSelectedCost,
    onlyOwned,
    setOnlyOwned,
    resetFilters,
  } = useCardSearch();

  const [selectedModalCard, setSelectedModalCard] = useState<PokemonCard | null>(null);

  const handleSuggestion = (term: string) => {
    setSearchQuery(term);
    void handleSearch();
  };

  const ownedCountInPage = results.filter((c) => (c.owned_copies ?? 0) > 0).length;

  return (
    <div className="w-full text-slate-100 flex flex-col gap-6" data-testid="search-cards-screen">
      {/* Encabezado adaptable según el rol (Jugador o Admin) */}
      <section className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-2 border-b border-arena-border/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-2 h-2 rounded-full ${mode === 'player' ? 'bg-emerald-400' : 'bg-blue-500'}`} />
            <span className={`text-[11px] font-semibold tracking-wider uppercase ${mode === 'player' ? 'text-emerald-400' : 'text-blue-400'}`}>
              {mode === 'player' ? 'Catálogo & Colección del Jugador' : 'Catálogo de Cartas · Entorno Administrativo'}
            </span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            {mode === 'player' ? (
              <>
                <BookOpen className="w-6 h-6 text-amber-400" />
                <span>Catálogo de Cartas & Mi Colección</span>
              </>
            ) : (
              <span>Buscador y Consulta de Cartas</span>
            )}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {mode === 'player'
              ? 'Explora todas las cartas disponibles en Poké-Arena, consulta tus copias poseídas y filtra por tipo, costo y colección.'
              : 'Explora y administra todas las cartas registradas en la arena.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {mode === 'player' && (
            <div className="px-3 py-1.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-xs text-emerald-300 font-mono flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5" />
              <span>En esta vista: <strong>{ownedCountInPage}</strong> poseídas</span>
            </div>
          )}
          {totalResults > 0 && (
            <div className="px-3 py-1.5 rounded-xl bg-[#0F172A]/80 border border-white/10 text-xs text-slate-300 font-mono">
              Total en catálogo: <strong className="text-amber-300">{totalResults}</strong>
            </div>
          )}
        </div>
      </section>

      {/* Barra de Filtros y Búsqueda con Costo y Colección Propia */}
      <section>
        <SearchBar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSubmit={handleSearch}
          onClear={handleClear}
          isLoading={isLoading}
          selectedType={selectedType}
          onSelectType={setSelectedType}
          selectedRarity={selectedRarity}
          onSelectRarity={setSelectedRarity}
          selectedCost={selectedCost}
          onSelectCost={setSelectedCost}
          onlyOwned={onlyOwned}
          onToggleOnlyOwned={setOnlyOwned}
          onResetFilters={resetFilters}
        />
      </section>

      {/* Manejo de Error 503 / Catálogo no disponible o Fallo de Red */}
      {error && (
        <section
          className="p-4 rounded-2xl border border-red-500/40 bg-red-950/30 text-red-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg"
          data-testid="search-catalog-error"
        >
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-xl bg-red-900/50 border border-red-500/50 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-4 h-4 text-red-400" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-red-100">
                {isCatalogUnavailable
                  ? "Catálogo temporalmente no disponible"
                  : "Error al consultar el catálogo"}
              </h4>
              <p className="text-xs text-red-300/90 mt-0.5">
                {error}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={reload}
            disabled={isLoading}
            className="px-4 py-2 bg-red-600 hover:bg-red-500 active:bg-red-700 text-white rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-50 shrink-0 cursor-pointer"
            data-testid="search-retry-button"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Reintentar catálogo</span>
          </button>
        </section>
      )}

      {/* Sección de Resultados o Pantalla Inicial */}
      <section className="flex-1 flex flex-col">
        {!hasSearched && !isLoading ? (
          <div className="my-auto py-8">
            <EmptyState onSuggestSearch={handleSuggestion} />
          </div>
        ) : (
          <CardGrid
            cards={results}
            isLoading={isLoading}
            totalResults={totalResults}
            currentPage={currentPage}
            totalPages={totalPages}
            onSelectCard={(card) => setSelectedModalCard(card)}
            onNextPage={nextPage}
            onPrevPage={prevPage}
            onGoToPage={goToPage}
          />
        )}
      </section>

      {/* Modal Detalle de Carta en Alta Resolución */}
      <CardDetailModal
        card={selectedModalCard}
        onClose={() => setSelectedModalCard(null)}
      />
    </div>
  );
};

