import React, { useState } from 'react';
import { X, Sparkles, Shield, Zap, Flame, CheckCircle, Info } from 'lucide-react';
import { PokemonCard, CardType, CardRarity } from '../../types/card.types';
import { useCardThumbnail } from '../../hooks/useCardThumbnail';

interface CardDetailModalProps {
  card: PokemonCard | null;
  onClose: () => void;
}

const TYPE_CONFIG: Record<
  CardType,
  { label: string; badgeClass: string; glowClass: string }
> = {
  FUE: {
    label: 'Fuego',
    badgeClass: 'bg-red-500/20 text-red-400 border-red-500/40',
    glowClass: 'shadow-red-500/20',
  },
  AGU: {
    label: 'Agua',
    badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    glowClass: 'shadow-blue-500/20',
  },
  PLA: {
    label: 'Planta',
    badgeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    glowClass: 'shadow-emerald-500/20',
  },
  ELE: {
    label: 'Eléctrico',
    badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    glowClass: 'shadow-amber-500/20',
  },
  PSI: {
    label: 'Psíquico',
    badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
    glowClass: 'shadow-purple-500/20',
  },
  LUC: {
    label: 'Lucha',
    badgeClass: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
    glowClass: 'shadow-orange-500/20',
  },
};

const DEFAULT_TYPE_CONFIG = {
  label: 'Normal',
  badgeClass: 'bg-slate-500/20 text-slate-300 border-slate-500/40',
  glowClass: 'shadow-slate-500/20',
};

const RARITY_BADGE: Record<CardRarity, { label: string; class: string }> = {
  COMUN: { label: 'Común', class: 'text-slate-400 border-slate-700 bg-slate-800/40' },
  POCO_COMUN: { label: 'Poco Común', class: 'text-emerald-400 border-emerald-800/40 bg-emerald-950/30' },
  RARA: { label: 'Rara', class: 'text-blue-400 border-blue-800/40 bg-blue-950/30' },
  LEGENDARIA: { label: 'Legendaria', class: 'text-amber-400 border-amber-500/50 bg-amber-950/40 font-bold' },
};

export const CardDetailModal: React.FC<CardDetailModalProps> = ({ card, onClose }) => {
  if (!card) return null;

  const thumbnail = useCardThumbnail(card.id);
  const [failedThumbnail, setFailedThumbnail] = useState<string | null>(null);
  const typeConfig = TYPE_CONFIG[card.type] || DEFAULT_TYPE_CONFIG;
  const rarityConfig = RARITY_BADGE[card.rarity] || RARITY_BADGE.COMUN;
  const isOwned = (card.owned_copies ?? 0) > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in"
      onClick={onClose}
      data-testid="card-detail-modal"
    >
      <div
        className="relative w-full max-w-2xl bg-arena-card border border-arena-border rounded-3xl p-6 md:p-8 shadow-2xl overflow-hidden flex flex-col md:flex-row gap-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Botón de cerrar */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-xl bg-slate-800/70 border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors z-10"
          aria-label="Cerrar modal"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Vista grande de la imagen de la carta */}
        <div className="w-full md:w-1/2 flex flex-col items-center justify-center">
          <div className={`relative aspect-[5/7] w-full max-w-[280px] bg-slate-900 rounded-2xl overflow-hidden border-2 border-arena-border shadow-2xl ${typeConfig.glowClass} flex items-center justify-center p-2`}>
            {thumbnail && thumbnail !== failedThumbnail ? (
              <img
                src={thumbnail}
                alt={card.name}
                onError={() => setFailedThumbnail(thumbnail)}
                className="w-full h-full object-contain drop-shadow-2xl"
              />
            ) : (
              <div className="flex flex-col items-center justify-center p-6 text-center">
                <Sparkles className="w-12 h-12 text-slate-500 mb-3" />
                <span className="text-sm text-slate-300 font-bold">{card.name}</span>
                <span className="text-xs text-slate-500">{card.code}</span>
              </div>
            )}

            {/* Insignia de Costo */}
            <div className="absolute top-3 left-3 flex items-center justify-center w-9 h-9 rounded-full bg-slate-950/90 border-2 border-amber-400 shadow-lg backdrop-blur-sm">
              <span className="text-sm font-black text-amber-300">{card.cost}</span>
            </div>

            {/* Insignia de Tipo */}
            <div
              className={`absolute top-3 right-3 px-2.5 py-1 rounded-full border text-xs font-bold backdrop-blur-sm ${typeConfig.badgeClass}`}
            >
              {typeConfig.label}
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 text-center font-mono">
            {card.code} · Vista de alta resolución
          </p>
        </div>

        {/* Información y Atributos detallados */}
        <div className="w-full md:w-1/2 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs px-2.5 py-0.5 rounded-full border ${rarityConfig.class}`}>
                {rarityConfig.label}
              </span>
              <span className={`text-xs px-2.5 py-0.5 rounded-full border ${typeConfig.badgeClass}`}>
                {typeConfig.label}
              </span>
            </div>

            <h3 className="text-2xl font-black text-slate-100 mt-1">
              {card.name}
            </h3>

            {card.description && (
              <p className="text-xs text-slate-300 mt-2 leading-relaxed bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                {card.description}
              </p>
            )}

            {/* Atributos numéricos */}
            <div className="grid grid-cols-3 gap-2 mt-4">
              <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl flex flex-col items-center">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Costo</span>
                <span className="text-lg font-black text-amber-300 mt-0.5">{card.cost}</span>
              </div>
              <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl flex flex-col items-center">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1">
                  <Zap className="w-3 h-3 text-red-400" /> Poder
                </span>
                <span className="text-lg font-black text-red-400 mt-0.5">{card.power}</span>
              </div>
              <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl flex flex-col items-center">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1">
                  <Shield className="w-3 h-3 text-emerald-400" /> Vida
                </span>
                <span className="text-lg font-black text-emerald-400 mt-0.5">{card.hp}</span>
              </div>
            </div>

            {/* Habilidad */}
            <div className="mt-4 p-3 rounded-xl bg-indigo-950/30 border border-indigo-500/30">
              <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-300 mb-1">
                <Flame className="w-4 h-4 text-indigo-400" />
                <span>Habilidad: {card.ability_name || card.ability_code || 'Ataque Directo'}</span>
              </div>
              <p className="text-[11px] text-indigo-200/80">
                {card.ability_code ? `Identificador técnico [${card.ability_code}]. Habilidad pasiva o activa en batalla.` : 'Esta carta cuenta con habilidades de combate elementales.'}
              </p>
            </div>
          </div>

          {/* Estado en Colección del Jugador */}
          <div className="mt-6 pt-4 border-t border-arena-border">
            <div className={`p-3 rounded-xl border flex items-center gap-3 ${
              isOwned
                ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                : 'bg-slate-900/60 border-slate-800 text-slate-400'
            }`}>
              {isOwned ? (
                <>
                  <CheckCircle className="w-6 h-6 text-emerald-400 shrink-0" />
                  <div>
                    <h5 className="text-xs font-bold text-emerald-200">En tu Colección</h5>
                    <p className="text-[11px] text-emerald-300/80">
                      Posees <strong className="text-white">{card.owned_copies}</strong> copia(s) disponibles para tus barajas.
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <Info className="w-6 h-6 text-slate-500 shrink-0" />
                  <div>
                    <h5 className="text-xs font-bold text-slate-300">Carta no adquirida</h5>
                    <p className="text-[11px] text-slate-400">
                      Aún no posees copias de esta carta en tu colección.
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

