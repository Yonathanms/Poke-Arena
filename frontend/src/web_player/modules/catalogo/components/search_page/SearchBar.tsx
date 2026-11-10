import React from 'react';
import { Search, X, Loader2, Sparkles, CheckSquare, Square, RotateCcw } from 'lucide-react';
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
  selectedCost?: number | 'ALL';
  onSelectCost?: (cost: number | 'ALL') => void;
  onlyOwned?: boolean;
  onToggleOnlyOwned?: (onlyOwned: boolean) => void;
  onResetFilters?: () => void;
}

const TYPE_OPTIONS: { label: string; value: CardType | 'ALL'; colorClass?: string }[] = [
  { label: 'Todos', value: 'ALL' },
  { label: 'Fuego', value: 'FUE', colorClass: 'text-red-400 border-red-500/30' },
  { label: 'Agua', value: 'AGU', colorClass: 'text-blue-400 border-blue-500/30' },
  { label: 'Planta', value: 'PLA', colorClass: 'text-emerald-400 border-emerald-500/30' },
  { label: 'Eléctrico', value: 'ELE', colorClass: 'text-amber-400 border-amber-500/30' },
  { label: 'Psíquico', value: 'PSI', colorClass: 'text-purple-400 border-purple-500/30' },
  { label: 'Lucha', value: 'LUC', colorClass: 'text-orange-400 border-orange-500/30' },
];

const RARITY_OPTIONS: { label: string; value: CardRarity | 'ALL' }[] = [
  { label: 'Todas', value: 'ALL' },
  { label: 'Común', value: 'COMUN' },
  { label: 'Poco Común', value: 'POCO_COMUN' },
  { label: 'Rara', value: 'RARA' },
  { label: 'Legendaria', value: 'LEGENDARIA' },
];

const COST_OPTIONS: { label: string; value: number | 'ALL' }[] = [
  { label: 'Todos', value: 'ALL' },
  { label: '0', value: 0 },
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '3', value: 3 },
  { label: '4', value: 4 },
  { label: '5', value: 5 },
  { label: '6+', value: 6 },
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
  selectedCost = 'ALL',
  onSelectCost,
  onlyOwned = false,
  onToggleOnlyOwned,
  onResetFilters,
}) => {
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    selectedType !== 'ALL' ||
    selectedRarity !== 'ALL' ||
    selectedCost !== 'ALL' ||
    onlyOwned;

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

      {/* Filtros combinables: Tipo, Costo, Rareza y Solo Propias */}
      <div className="mt-4 pt-4 border-t border-arena-border/50 flex flex-col gap-3.5 text-xs md:text-sm">
        {/* Fila 1: Filtro por Tipo */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-slate-400 font-semibold mr-1 w-12 shrink-0">Tipo:</span>
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
                      ? 'bg-blue-600/30 border-blue-500 text-blue-300 font-semibold shadow-sm'
                      : 'bg-arena-surface/60 border-arena-border text-slate-400 hover:text-slate-200 hover:border-slate-600'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Fila 2: Filtro por Costo de Energía */}
        {onSelectCost && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-400 font-semibold mr-1 w-12 shrink-0">Costo:</span>
            <div className="flex flex-wrap gap-1.5">
              {COST_OPTIONS.map((item) => {
                const active = selectedCost === item.value;
                return (
                  <button
                    key={String(item.value)}
                    type="button"
                    onClick={() => onSelectCost(item.value)}
                    className={`px-2.5 py-1 rounded-lg border text-xs font-medium transition-all ${
                      active
                        ? 'bg-amber-500/20 border-amber-400 text-amber-300 font-bold shadow-sm'
                        : 'bg-arena-surface/60 border-arena-border text-slate-400 hover:text-slate-200 hover:border-slate-600'
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Fila 3: Rareza, Filtro de Colección Propia y Limpiar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <div className="flex flex-wrap items-center gap-4">
            {/* Selector de Rareza */}
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

            {/* Switch / Toggle "Solo cartas propias" */}
            {onToggleOnlyOwned && (
              <button
                type="button"
                onClick={() => onToggleOnlyOwned(!onlyOwned)}
                data-testid="filter-only-owned"
                className={`flex items-center gap-2 px-3 py-1 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
                  onlyOwned
                    ? 'bg-emerald-950/60 border-emerald-500/60 text-emerald-300 shadow-sm'
                    : 'bg-arena-surface border-arena-border text-slate-400 hover:text-slate-300 hover:border-slate-600'
                }`}
              >
                {onlyOwned ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-slate-500" />
                )}
                <span>Solo cartas en mi colección</span>
              </button>
            )}
          </div>

          {/* Botón para reiniciar todos los filtros si alguno está activo */}
          {hasActiveFilters && onResetFilters && (
            <button
              type="button"
              onClick={onResetFilters}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-amber-400 transition-colors px-2 py-1 rounded-lg hover:bg-slate-800/50"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Limpiar filtros</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

