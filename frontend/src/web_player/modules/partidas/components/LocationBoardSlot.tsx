/** Tarjeta TCG de estadio en el tablero central (estilo CreateLocationScreen + arte con Bearer). */

import React, { useState } from "react";
import { MapPin, Shield, Sparkles, Zap } from "lucide-react";
import { useLocationImage } from "../hooks/useLocationImage";
import {
  formatLocationEffectSummary,
  type MatchCardDTO,
  type MatchLocationDTO,
} from "../types/partidas.types";

export interface LocationBoardSlotProps {
  readonly location: MatchLocationDTO;
  readonly index: number;
}

function BoardCardMiniChip({
  card,
  isMine,
}: {
  readonly card: MatchCardDTO;
  readonly isMine: boolean;
}): React.ReactElement {
  return (
    <div
      className={`rounded-lg px-2 py-1.5 border text-[11px] flex items-center justify-between gap-2 ${
        isMine
          ? "bg-blue-500/15 border-blue-400/40 text-blue-100"
          : "bg-red-500/10 border-red-400/30 text-red-100"
      }`}
    >
      <span className="font-semibold truncate">{card.name}</span>
      <span className="font-mono font-bold text-amber-300 shrink-0">{card.power}</span>
    </div>
  );
}

export function LocationBoardSlot({
  location,
  index,
}: LocationBoardSlotProps): React.ReactElement {
  const imageUrl = useLocationImage(location.id);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const effectSummary = formatLocationEffectSummary(location);
  const isBlockedZone = location.card_limit === 0;

  return (
    <section className="glass-card overflow-hidden flex flex-col">
      {/* Zona superior: cartas del rival */}
      <div className="bg-[#090D16]/80 border-b border-white/10 px-3.5 py-2.5 flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
          <span>Lado rival</span>
          <span>
            {isBlockedZone
              ? "Sin espacio"
              : `${location.opponent_cards.length} / ${location.card_limit}`}
          </span>
        </div>

        {location.opponent_cards.length > 0 ? (
          <div className="grid grid-cols-2 gap-1.5">
            {location.opponent_cards.map((card, cardIdx) => (
              <BoardCardMiniChip key={`${card.id}-${cardIdx}`} card={card} isMine={false} />
            ))}
          </div>
        ) : (
          <div className="h-8 rounded-lg border border-dashed border-white/10 flex items-center justify-center text-[11px] text-slate-500">
            {isBlockedZone ? "Zona cerrada para cartas" : "Espacios disponibles"}
          </div>
        )}
      </div>

      {/* Arte 4:3 + insignias de energía y límite */}
      <div className="p-3.5 flex flex-col gap-3 flex-1">
        <div className="relative aspect-[4/3] w-full overflow-hidden rounded-xl border border-white/10 bg-[#090D16]/90">
          {imageUrl && imageUrl !== failedUrl ? (
            <img
              src={imageUrl}
              alt={location.nombre}
              onError={() => setFailedUrl(imageUrl)}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-slate-500 p-4 text-center">
              <MapPin className="w-7 h-7 text-slate-600" />
              <span className="text-xs font-semibold text-slate-400">{location.nombre}</span>
            </div>
          )}

          {/* Energía de ubicación (arriba izquierda) */}
          <div className="absolute top-2 left-2 rounded-lg bg-slate-950/85 backdrop-blur-sm border border-white/15 px-2.5 py-1 text-[11px] font-bold text-amber-300 flex items-center gap-1">
            <Zap className="w-3 h-3 text-amber-400" />
            <span>
              {location.energia_tipo === "FIJA"
                ? `+${location.energia_valor} Energía fija`
                : `+${location.energia_valor} / carta`}
            </span>
          </div>

          {/* Límite de cartas (arriba derecha) */}
          <div className="absolute top-2 right-2 rounded-lg bg-slate-950/85 backdrop-blur-sm border border-white/15 px-2.5 py-1 text-[11px] font-semibold text-slate-200 flex items-center gap-1">
            <Shield className="w-3 h-3 text-blue-400" />
            <span>{isBlockedZone ? "Sin espacio" : `Máx. ${location.card_limit} cartas`}</span>
          </div>
        </div>

        {/* Título y descripción */}
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-base font-extrabold tracking-tight text-white truncate">
              {location.nombre}
            </h3>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 shrink-0">
              Estadio {index + 1}
            </span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed line-clamp-2">
            {location.descripcion}
          </p>
        </div>

        {/* Regla activa */}
        <div className="mt-auto rounded-xl border border-blue-500/20 bg-blue-950/25 px-3 py-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Sparkles className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span className="text-[11px] font-semibold text-blue-200 truncate">
              {effectSummary}
            </span>
          </div>
          <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-bold text-blue-300 shrink-0">
            REGLA
          </span>
        </div>
      </div>

      {/* Zona inferior: cartas propias */}
      <div className="bg-[#090D16]/80 border-t border-white/10 px-3.5 py-2.5 flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-blue-300/90">
          <span>Tu lado</span>
          <span>
            {isBlockedZone
              ? "Sin espacio"
              : `${location.my_cards.length} / ${location.card_limit}`}
          </span>
        </div>

        {location.my_cards.length > 0 ? (
          <div className="grid grid-cols-2 gap-1.5">
            {location.my_cards.map((card, cardIdx) => (
              <BoardCardMiniChip key={`${card.id}-${cardIdx}`} card={card} isMine={true} />
            ))}
          </div>
        ) : (
          <div className="h-8 rounded-lg border border-dashed border-blue-500/25 flex items-center justify-center text-[11px] text-slate-400">
            {isBlockedZone ? "No admite cartas" : "Listo para desplegar"}
          </div>
        )}
      </div>
    </section>
  );
}
