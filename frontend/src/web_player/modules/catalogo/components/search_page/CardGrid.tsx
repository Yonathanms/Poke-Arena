import React from 'react';
import { PokemonCard } from '../../types/card.types';
import { CardItem } from './CardItem';
import { AlertCircle } from 'lucide-react';

interface CardGridProps {
  cards: PokemonCard[];
  isLoading: boolean;
  onSelectCard?: (card: PokemonCard) => void;
}

export const CardGrid: React.FC<CardGridProps> = ({ cards, isLoading, onSelectCard }) => {
  if (isLoading) {
    return (
      <div className="w-full">
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
      <div className="flex flex-col items-center justify-center p-12 text-center bg-arena-card/40 border border-arena-border rounded-2xl">
        <AlertCircle className="w-10 h-10 text-amber-400 mb-3" />
        <h4 className="text-lg font-semibold text-slate-100">No se encontraron cartas</h4>
        <p className="text-sm text-slate-400 mt-1 max-w-sm">
          Intenta con otro término o elimina los filtros de tipo y rareza.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between text-xs text-slate-400 px-1">
        <span>Mostrando {cards.length} cartas (máximo 15 por página · 3x5)</span>
        <span className="text-emerald-400 font-medium">Búsqueda completada</span>
      </div>

      {/* Rejilla de 15 cartas: 5 columnas en pantallas de escritorio / 3 filas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {cards.map((card) => (
          <CardItem key={card.id} card={card} onSelect={onSelectCard} />
        ))}
      </div>
    </div>
  );
};
