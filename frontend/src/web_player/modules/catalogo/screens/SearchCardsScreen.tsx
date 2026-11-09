import React, { useState } from 'react';
import { useCardSearch } from '../hooks/useCardSearch';
import { useCardThumbnail } from '../hooks/useCardThumbnail';
import { SearchBar, CardGrid, EmptyState } from '../components/search_page';
import { PokemonCard } from '../types/card.types';
import { Sparkles, X, Shield, Zap, RefreshCw, AlertTriangle } from 'lucide-react';

function CardDetailThumbnail({ card }: { card: PokemonCard }) {
  const thumbnail = useCardThumbnail(card.id);
  const [failedThumbnail, setFailedThumbnail] = useState<string | null>(null);
  if (!thumbnail || thumbnail === failedThumbnail) {
    return <Sparkles className="w-8 h-8 text-slate-600" />;
  }
  return (
    <img
      src={thumbnail}
      alt={card.name}
      onError={() => setFailedThumbnail(thumbnail)}
      className="w-full h-full object-contain p-1"
    />
  );
}

export const SearchCardsScreen: React.FC = () => {
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
  } = useCardSearch();

  const [selectedModalCard, setSelectedModalCard] = useState<PokemonCard | null>(null);

  const handleSuggestion = (term: string) => {
    setSearchQuery(term);
    // Ejecutar búsqueda inmediata con el término sugerido
    void handleSearch();
  };

  return (
    <div className="w-full text-slate-100 flex flex-col gap-6" data-testid="search-cards-screen">
      {/* Encabezado del Buscador en el Entorno Administrativo */}
      <section className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-2 border-b border-arena-border/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="text-[11px] font-semibold tracking-wider text-blue-400 uppercase">
              Catálogo de Cartas · Entorno Administrativo
            </span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-100">
            Buscador y Consulta de Cartas
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Consulta el catálogo persistido en MongoDB con filtros en tiempo real y paginación de servidor.
          </p>
        </div>

        {totalResults > 0 && (
          <div className="self-start md:self-auto px-3 py-1.5 rounded-xl bg-arena-card border border-arena-border text-xs text-slate-300 font-mono">
            Total indexadas: <strong className="text-amber-300">{totalResults}</strong>
          </div>
        )}
      </section>

      {/* Barra de Filtros y Búsqueda */}
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
                  ? "Catálogo temporalmente no disponible (503)"
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

      {/* Modal Detalle de Carta */}
      {selectedModalCard && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setSelectedModalCard(null)}
          data-testid="card-detail-modal"
        >
          <div
            className="relative w-full max-w-lg bg-arena-card border border-arena-border rounded-3xl p-6 shadow-2xl flex flex-col gap-4 text-slate-100"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setSelectedModalCard(null)}
              className="absolute top-4 right-4 p-2 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
              aria-label="Cerrar detalle"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex gap-4 items-start">
              <div className="w-28 aspect-[5/7] bg-slate-900 rounded-xl overflow-hidden border border-arena-border shrink-0 flex items-center justify-center">
                <CardDetailThumbnail key={selectedModalCard.id} card={selectedModalCard} />
              </div>

              <div className="flex-1 min-w-0">
                <span className="text-[10px] font-mono text-slate-400">
                  {selectedModalCard.code}
                </span>
                <h3 className="text-xl font-bold text-slate-50 truncate">
                  {selectedModalCard.name}
                </h3>
                <div className="flex flex-wrap gap-2 mt-2">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold border border-blue-500/40 bg-blue-500/20 text-blue-300">
                    {selectedModalCard.type}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold border border-slate-700 bg-slate-800/40 text-slate-300">
                    {selectedModalCard.rarity}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold border border-amber-500/40 bg-amber-500/20 text-amber-300">
                    {selectedModalCard.cost} Costo
                  </span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 py-3 border-y border-arena-border/60 text-xs">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-red-400" />
                <span>Poder Ataque: <strong className="text-slate-200">{selectedModalCard.power}</strong></span>
              </div>
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-400" />
                <span>Puntos de Vida: <strong className="text-slate-200">{selectedModalCard.hp}</strong></span>
              </div>
              {selectedModalCard.ability_code && (
                <div className="col-span-2 text-slate-400">
                  Habilidad: <strong className="text-slate-200 font-mono">{selectedModalCard.ability_code}</strong>
                </div>
              )}
            </div>

            {selectedModalCard.description && (
              <p className="text-xs text-slate-300 italic">
                "{selectedModalCard.description}"
              </p>
            )}

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setSelectedModalCard(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
