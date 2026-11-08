import React from 'react';
import { Search, X, Loader2, Sparkles } from 'lucide-react';
import { CardType, CardRarity } from '../../types/card.types';

interface SearchBarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onSubmit: (e?: React.FormEvent) => void;
  onClear: () => void;
  isLoading: boolean;
  selectedType: CardType | 'ALL';
  onSelectType: (type: CardType | 'ALL') => void;
  selectedRarity: CardRarity | 'ALL';
  onSelectRarity: (rarity: CardRarity | 'ALL') => void;
}

const TYPE_OPTIONS: { label: string; value: CardType | 'ALL'; colorClass?: string }[] = [
  { label: 'Todos', value: 'ALL' },
  { label: 'Fuego', value: 'FUE', colorClass: 'text-red-400 border-red-500/30' },
  { label: 'Agua', value: 'AGU', colorClass: 'text-blue-400 border-blue-500/30' },
  { label: 'Planta', value: 'PLA', colorClass: 'text-emerald-400 border-emerald-500/30' },
  { label: 'Eléctrico', value: 'ELE', colorClass: 'text-amber-400 border-amber-500/30' },
  { label: 'Psíquico', value: 'PSI', colorClass: 'text-purple-400 border-purple-500/30' },
  { label: 'Lucha', value: 'LUC', colorClass: 'text-orange-400 border-orange-500/30' },
  { label: 'Incoloro', value: 'INC', colorClass: 'text-slate-400 border-slate-500/30' },
];

const RARITY_OPTIONS: { label: string; value: CardRarity | 'ALL' }[] = [
  { label: 'Todas', value: 'ALL' },
  { label: 'Común', value: 'COMUN' },
  { label: 'Infrecuente', value: 'INFRECUENTE' },
  { label: 'Rara', value: 'RARA' },
  { label: 'Épica', value: 'EPICA' },
  { label: 'Legendaria', value: 'LEGENDARIA' },
];

export const SearchBar: React.FC<SearchBarProps> = ({
  searchQuery,
  onSearchChange,
  onSubmit,
  onClear,
  isLoading,
  selectedType,
  onSelectType,
  selectedRarity,
  onSelectRarity,
}) => {
  return (
    <div className="w-full bg-arena-card border border-arena-border rounded-2xl p-4 md:p-6 shadow-xl backdrop-blur-sm">
      <form onSubmit={onSubmit} className="flex flex-col md:flex-row gap-3 items-stretch">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400">
            <Search className="w-5 h-5" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Buscar por nombre (ej. Charizard, Pikachu), código o habilidad..."
            className="w-full pl-11 pr-10 py-3.5 bg-arena-surface border border-arena-border text-slate-100 placeholder-slate-400 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-sm md:text-base"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={onClear}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition-colors"
              aria-label="Limpiar búsqueda"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="px-6 py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-[0.98] text-white font-medium rounded-xl shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Buscando...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5 text-amber-300" />
              <span>Buscar Cartas</span>
            </>
          )}
        </button>
      </form>

      {/* Filtros complementarios rápidos */}
      <div className="mt-4 pt-4 border-t border-arena-border/50 flex flex-wrap gap-4 items-center justify-between text-xs md:text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-slate-400 font-medium mr-1">Tipo:</span>
          <div className="flex flex-wrap gap-1.5">
            {TYPE_OPTIONS.map((item) => {
              const active = selectedType === item.value;
              return (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => onSelectType(item.value)}
                  className={`px-2.5 py-1 rounded-lg border text-xs font-medium transition-all ${
                    active
                      ? 'bg-blue-600/30 border-blue-500 text-blue-300 font-semibold'
                      : 'bg-arena-surface/60 border-arena-border text-slate-400 hover:text-slate-200 hover:border-slate-600'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Rareza:</span>
          <select
            value={selectedRarity}
            onChange={(e) => onSelectRarity(e.target.value as CardRarity | 'ALL')}
            className="bg-arena-surface border border-arena-border text-slate-200 text-xs rounded-lg px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {RARITY_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
};
