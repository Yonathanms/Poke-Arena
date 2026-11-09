import React from 'react';
import { PokemonCard } from '../../types/card.types';
import { CardItem } from './CardItem';
import { AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';

interface CardGridProps {
  cards: PokemonCard[];
  isLoading: boolean;
  totalResults?: number;
  currentPage?: number;
  totalPages?: number;
  onSelectCard?: (card: PokemonCard) => void;
  onNextPage?: () => void;
  onPrevPage?: () => void;
  onGoToPage?: (page: number) => void;
}

export const CardGrid: React.FC<CardGridProps> = ({
  cards,
  isLoading,
  totalResults,
  currentPage = 1,
  totalPages = 1,
  onSelectCard,
  onNextPage,
  onPrevPage,
}) => {
  if (isLoading) {
    return (
      <div className="w-full space-y-4" data-testid="card-grid-loading">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {Array.from({ length: 15 }).map((_, index) => (
            <div
              key={index}
              className="bg-arena-card/60 border border-arena-border rounded-2xl p-3 animate-pulse flex flex-col"
            >
              <div className="aspect-[5/7] w-full bg-slate-800/80 rounded-xl mb-3" />
              <div className="h-4 bg-slate-800 rounded w-3/4 mb-2" />
              <div className="h-3 bg-slate-800 rounded w-1/2 mb-3" />
              <div className="mt-auto h-4 bg-slate-800 rounded w-full" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center p-12 text-center bg-arena-card/40 border border-arena-border rounded-2xl"
        data-testid="card-grid-empty"
      >
        <AlertCircle className="w-10 h-10 text-amber-400 mb-3" />
        <h4 className="text-lg font-semibold text-slate-100">No se encontraron cartas</h4>
        <p className="text-sm text-slate-400 mt-1 max-w-sm">
          Intenta con otro término o elimina los filtros de tipo y rareza.
        </p>
      </div>
    );
  }

  const effectiveTotal = totalResults ?? cards.length;

  return (
    <div className="w-full space-y-6" data-testid="card-grid-container">
      {/* Barra de estado superior */}
      <div className="flex flex-wrap items-center justify-between text-xs text-slate-400 px-1 gap-2">
        <span>
          Mostrando <strong className="text-slate-200">{cards.length}</strong> de{" "}
          <strong className="text-slate-200">{effectiveTotal}</strong> cartas encontradas
        </span>
        <span className="text-emerald-400 font-medium flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          Página {currentPage} de {totalPages}
        </span>
      </div>

      {/* Rejilla de 15 cartas: 5 columnas en pantallas de escritorio / 3 filas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {cards.map((card) => (
          <CardItem key={card.id} card={card} onSelect={onSelectCard} />
        ))}
      </div>

      {/* Controles de paginación de servidor */}
      {totalPages > 1 && (
        <div
          className="flex flex-wrap items-center justify-between border-t border-arena-border/60 pt-4 px-2 gap-3"
          data-testid="card-grid-pagination"
        >
          <div className="text-xs text-slate-400">
            Total en catálogo: <span className="font-semibold text-slate-200">{effectiveTotal} cartas</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onPrevPage}
              disabled={currentPage <= 1 || isLoading}
              className="px-3 py-1.5 rounded-lg border border-arena-border bg-arena-surface hover:bg-slate-800 text-slate-200 text-xs font-semibold flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              aria-label="Página anterior"
              data-testid="pagination-prev"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Anterior</span>
            </button>

            <span
              className="px-3 py-1 text-xs font-mono font-bold text-slate-300 bg-arena-card border border-arena-border rounded-lg"
              data-testid="pagination-page-indicator"
            >
              {currentPage} / {totalPages}
            </span>

            <button
              type="button"
              onClick={onNextPage}
              disabled={currentPage >= totalPages || isLoading}
              className="px-3 py-1.5 rounded-lg border border-arena-border bg-arena-surface hover:bg-slate-800 text-slate-200 text-xs font-semibold flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              aria-label="Página siguiente"
              data-testid="pagination-next"
            >
              <span>Siguiente</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
