import React, { useState } from 'react';
import { Shield, Zap, Sparkles, ShoppingBag } from 'lucide-react';
import { PokemonCard, CardType, CardRarity } from '../../types/card.types';

interface CardItemProps {
  card: PokemonCard;
  onSelect?: (card: PokemonCard) => void;
}

const TYPE_CONFIG: Record<
  CardType,
  { label: string; badgeClass: string; glowClass: string }
> = {
  FUE: {
    label: 'Fuego',
    badgeClass: 'bg-red-500/20 text-red-400 border-red-500/40',
    glowClass: 'group-hover:shadow-red-500/20',
  },
  AGU: {
    label: 'Agua',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    glowClass: 'group-hover:shadow-blue-500/20',
  },
  PLA: {
    label: 'Planta',
    badgeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    glowClass: 'group-hover:shadow-emerald-500/20',
  },
  ELE: {
    label: 'Eléctrico',
    badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    glowClass: 'group-hover:shadow-amber-500/20',
  },
  PSI: {
    label: 'Psíquico',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    glowClass: 'group-hover:shadow-purple-500/20',
  },
  LUC: {
    label: 'Lucha',
    badgeClass: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
    glowClass: 'group-hover:shadow-orange-500/20',
  },
  INC: {
    label: 'Incoloro',
    badgeClass: 'bg-slate-500/20 text-slate-300 border-slate-500/40',
    glowClass: 'group-hover:shadow-slate-500/20',
  },
};

const RARITY_BADGE: Record<CardRarity, { label: string; class: string }> = {
  COMUN: { label: 'Común', class: 'text-slate-400 border-slate-700 bg-slate-800/40' },
  INFRECUENTE: { label: 'Infrecuente', class: 'text-emerald-400 border-emerald-800/40 bg-emerald-950/30' },
  RARA: { label: 'Rara', class: 'text-blue-400 border-blue-800/40 bg-blue-950/30' },
  EPICA: { label: 'Épica', class: 'text-purple-400 border-purple-800/40 bg-purple-950/30' },
  LEGENDARIA: { label: 'Legendaria', class: 'text-amber-400 border-amber-500/50 bg-amber-950/40 font-bold' },
};

export const CardItem: React.FC<CardItemProps> = ({ card, onSelect }) => {
  const [imageError, setImageError] = useState(false);
  const typeConfig = TYPE_CONFIG[card.type] || TYPE_CONFIG.INC;
  const rarityConfig = RARITY_BADGE[card.rarity] || RARITY_BADGE.COMUN;

  return (
    <div
      onClick={() => onSelect?.(card)}
      className={`group relative flex flex-col bg-arena-card border border-arena-border hover:border-blue-500/60 rounded-2xl p-3 transition-all duration-300 hover:-translate-y-1.5 shadow-lg hover:shadow-2xl ${typeConfig.glowClass} cursor-pointer overflow-hidden`}
    >
      {/* Relación de aspecto 5:7 para la imagen oficial */}
      <div className="relative aspect-[5/7] w-full bg-slate-900 rounded-xl overflow-hidden border border-arena-border/50 flex items-center justify-center">
        {!imageError ? (
          <img
            src={card.imageUrl}
            alt={card.name}
            onError={() => setImageError(true)}
            className="w-full h-full object-contain p-1 transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-4 text-center">
            <Sparkles className="w-8 h-8 text-slate-500 mb-2" />
            <span className="text-xs text-slate-400 font-semibold">{card.name}</span>
            <span className="text-[10px] text-slate-500">{card.code}</span>
          </div>
        )}

        {/* Insignia de Costo de Energía */}
        <div className="absolute top-2 left-2 flex items-center justify-center w-7 h-7 rounded-full bg-slate-950/80 border border-amber-400/60 shadow-md backdrop-blur-sm">
          <span className="text-xs font-black text-amber-300">{card.cost}</span>
        </div>

        {/* Insignia de Tipo */}
        <div
          className={`absolute top-2 right-2 px-2 py-0.5 rounded-full border text-[10px] font-bold backdrop-blur-sm ${typeConfig.badgeClass}`}
        >
          {typeConfig.label}
        </div>
      </div>

      {/* Metadatos y stats de la carta */}
      <div className="mt-2.5 flex flex-col flex-1 justify-between">
        <div>
          <div className="flex items-center justify-between gap-1">
            <span className="text-[10px] font-mono text-slate-400 tracking-wider">
              {card.code}
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded border ${rarityConfig.class}`}
            >
              {rarityConfig.label}
            </span>
          </div>
          <h4 className="text-sm font-bold text-slate-100 truncate mt-0.5 group-hover:text-blue-400 transition-colors">
            {card.name}
          </h4>
        </div>

        {/* Atributos: Poder & Vida */}
        <div className="mt-2 pt-2 border-t border-arena-border/50 flex items-center justify-between text-xs">
          <div className="flex items-center gap-1 text-red-400 font-medium">
            <Zap className="w-3.5 h-3.5 fill-red-400/20" />
            <span>{card.power} ATK</span>
          </div>
          <div className="flex items-center gap-1 text-emerald-400 font-medium">
            <Shield className="w-3.5 h-3.5 fill-emerald-400/20" />
            <span>{card.hp} HP</span>
          </div>
        </div>

        {/* Precio o acción de tienda si está disponible */}
        {card.price !== undefined && (
          <div className="mt-2 flex items-center justify-between pt-1">
            <span className="text-xs text-slate-400">Precio tienda</span>
            <div className="flex items-center gap-1 text-amber-300 font-bold text-xs">
              <ShoppingBag className="w-3 h-3" />
              <span>${card.price.toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
