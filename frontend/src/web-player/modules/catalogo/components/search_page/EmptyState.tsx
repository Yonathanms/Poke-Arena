import React from 'react';
import { Sparkles, Layers, ShieldCheck } from 'lucide-react';

interface EmptyStateProps {
  onSuggestSearch?: (term: string) => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onSuggestSearch }) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 md:p-14 text-center border-2 border-dashed border-arena-border/70 rounded-3xl bg-arena-card/40 backdrop-blur-sm transition-all">
      {/* Ilustración visual con temática de cartas Pokémon */}
      <div className="relative mb-6">
        <div className="w-28 h-36 md:w-36 md:h-48 rounded-2xl bg-gradient-to-br from-indigo-500/20 via-blue-500/10 to-purple-500/20 border-2 border-arena-border shadow-2xl flex flex-col items-center justify-center relative overflow-hidden group rotate-[-6deg] hover:rotate-0 transition-transform duration-300">
          <div className="w-16 h-16 rounded-full border-4 border-amber-400/40 flex items-center justify-center bg-slate-900/60 shadow-inner">
            <div className="w-6 h-6 rounded-full bg-amber-400/60" />
          </div>
          <span className="text-[10px] font-bold tracking-widest text-slate-400 mt-2 uppercase">POKÉ-ARENA</span>
        </div>

        {/* Tarjeta superpuesta para dar efecto de mazo */}
        <div className="absolute inset-0 w-28 h-36 md:w-36 md:h-48 rounded-2xl bg-gradient-to-br from-blue-600/30 to-indigo-800/30 border border-blue-500/40 shadow-xl flex flex-col items-center justify-center rotate-[8deg] -z-10 group-hover:rotate-6 transition-transform">
          <Sparkles className="w-8 h-8 text-blue-400/70 animate-pulse" />
        </div>
      </div>

      <h3 className="text-xl md:text-2xl font-bold text-slate-100 tracking-tight">
        Aquí aparecerán tus cartas
      </h3>

      <p className="mt-2 text-slate-400 max-w-md text-sm md:text-base leading-relaxed">
        Usa la barra superior para buscar cartas coleccionables por su nombre, tipo elemental o rareza.
      </p>

      {/* Sugerencias de búsqueda rápida */}
      {onSuggestSearch && (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Prueba buscando:</span>
          {['Charizard', 'Pikachu', 'Mewtwo', 'Agua', 'Legendaria'].map((term) => (
            <button
              key={term}
              onClick={() => onSuggestSearch(term)}
              className="px-3 py-1 rounded-full text-xs bg-arena-surface border border-arena-border text-blue-300 hover:bg-blue-600/20 hover:border-blue-400/50 transition-colors"
            >
              {term}
            </button>
          ))}
        </div>
      )}

      <div className="mt-8 grid grid-cols-2 gap-4 max-w-sm text-left">
        <div className="flex items-center gap-2.5 text-xs text-slate-400 bg-arena-surface/40 p-2.5 rounded-xl border border-arena-border/40">
          <Layers className="w-4 h-4 text-blue-400 shrink-0" />
          <span>Distribución fija 15 cartas (3x5)</span>
        </div>
        <div className="flex items-center gap-2.5 text-xs text-slate-400 bg-arena-surface/40 p-2.5 rounded-xl border border-arena-border/40">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Catálogo oficial verificado</span>
        </div>
      </div>
    </div>
  );
};
