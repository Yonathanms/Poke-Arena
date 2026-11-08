import React, { useState } from 'react';
import { useCardSearch } from '../hooks/useCardSearch';
import { SearchBar, CardGrid, EmptyState } from '../components/search_page';
import { PokemonCard } from '../types/card.types';
import { Sparkles, Layers, X, Shield, Zap, ShoppingBag } from 'lucide-react';

export const SearchCardsScreen: React.FC = () => {
  const {
    searchQuery,
    setSearchQuery,
    hasSearched,
    isLoading,
    results,
    handleSearch,
    handleClear,
    selectedType,
    setSelectedType,
    selectedRarity,
    setSelectedRarity,
  } = useCardSearch();

  const [selectedModalCard, setSelectedModalCard] = useState<PokemonCard | null>(null);

  // Cuando el timeout termina, se ejecuta la búsqueda, esto es un antipatrón, hay que arreglarlo.
  const handleSuggestion = (term: string) => {
    setSearchQuery(term);
    // Ejecutar la búsqueda de inmediato con la sugerencia
    setTimeout(() => {
      handleSearch();
    }, 50);
  };

  return (
    <div className="min-h-screen bg-arena-bg text-slate-100 flex flex-col">
      {/* Barra superior de navegación / Encabezado */}
      <header className="border-b border-arena-border bg-arena-card/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/30">
              <Sparkles className="w-5 h-5 text-amber-300" />
            </div>
            <div>
              <h1 className="text-lg font-black tracking-wider bg-gradient-to-r from-blue-400 via-indigo-300 to-amber-300 bg-clip-text text-transparent uppercase">
                Poké-Arena
              </h1>
              <p className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
                Tienda & Catálogo de Cartas
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-400 bg-arena-surface px-3 py-1.5 rounded-full border border-arena-border">
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            <span>Portal Jugador</span>
          </div>
        </div>
      </header>

      {/* Contenido Principal */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col gap-8">
        {/* Sección de Encabezado y Barra de Búsqueda */}
        <section className="flex flex-col gap-4">
          <div className="text-center md:text-left">
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-50">
              Buscador de Cartas
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Explora y encuentra cartas para tu mazo o adquiere nuevas cartas en la tienda.
            </p>
          </div>

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

        {/* Sección de Resultados o Pantalla Inicial */}
        <section className="flex-1 flex flex-col">
          {!hasSearched ? (
            <div className="my-auto py-8">
              <EmptyState onSuggestSearch={handleSuggestion} />
            </div>
          ) : (
            <CardGrid
              cards={results}
              isLoading={isLoading}
              onSelectCard={(card) => setSelectedModalCard(card)}
            />
          )}
        </section>
      </main>

      {/* Modal de Detalle de Carta (al pulsar una carta) */}
      {selectedModalCard && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-arena-card border border-arena-border rounded-3xl max-w-lg w-full p-6 relative shadow-2xl flex flex-col md:flex-row gap-6 animate-in fade-in zoom-in-95 duration-150">
            <button
              onClick={() => setSelectedModalCard(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-100 p-1.5 rounded-full bg-arena-surface hover:bg-slate-700 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="w-full md:w-1/2 aspect-[5/7] rounded-xl overflow-hidden bg-slate-900 border border-arena-border/50 flex items-center justify-center">
              <img
                src={selectedModalCard.imageUrl}
                alt={selectedModalCard.name}
                className="w-full h-full object-contain"
              />
            </div>

            <div className="w-full md:w-1/2 flex flex-col justify-between">
              <div>
                <span className="text-xs font-mono text-blue-400">{selectedModalCard.code}</span>
                <h3 className="text-xl font-bold text-slate-50 mt-1">
                  {selectedModalCard.name}
                </h3>
                <div className="flex gap-2 mt-2">
                  <span className="text-xs px-2 py-0.5 rounded-full border border-blue-500/40 bg-blue-500/10 text-blue-300">
                    {selectedModalCard.type}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full border border-amber-500/40 bg-amber-500/10 text-amber-300">
                    {selectedModalCard.rarity}
                  </span>
                </div>

                <p className="text-xs text-slate-300 mt-4 leading-relaxed">
                  {selectedModalCard.description || 'Sin descripción adicional.'}
                </p>

                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-arena-surface p-2 rounded-lg flex items-center gap-1.5 text-red-400 font-semibold">
                    <Zap className="w-4 h-4" />
                    <span>{selectedModalCard.power} ATK</span>
                  </div>
                  <div className="bg-arena-surface p-2 rounded-lg flex items-center gap-1.5 text-emerald-400 font-semibold">
                    <Shield className="w-4 h-4" />
                    <span>{selectedModalCard.hp} HP</span>
                  </div>
                </div>
              </div>

              {selectedModalCard.price !== undefined && (
                <div className="mt-6 pt-4 border-t border-arena-border flex items-center justify-between">
                  <div>
                    <span className="text-[10px] text-slate-400 block">Precio unitario</span>
                    <span className="text-lg font-bold text-amber-300">
                      ${selectedModalCard.price.toFixed(2)}
                    </span>
                  </div>
                  <button
                    onClick={() => alert(`Añadido al carrito: ${selectedModalCard.name}`)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl flex items-center gap-1.5 transition-colors shadow-lg shadow-blue-600/30"
                  >
                    <ShoppingBag className="w-4 h-4" />
                    Comprar
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
