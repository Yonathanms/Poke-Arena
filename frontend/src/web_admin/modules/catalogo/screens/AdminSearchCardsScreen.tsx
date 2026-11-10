/**
 * Pantalla administrativa de búsqueda y auditoría de cartas del catálogo (`AdminSearchCardsScreen.tsx`).
 *
 * Responsabilidades:
 * 1. Proporcionar a los usuarios con rol `PLATFORM_ADMIN` una herramienta integral y exclusiva
 *    para buscar, filtrar e inspeccionar todas las cartas registradas en la base de datos oficial.
 * 2. Diferenciarse explícitamente de la vista de jugador: NO muestra copias personales ni filtros
 *    de colección privada ("solo cartas propias").
 * 3. Permitir alternar entre vista de tarjetas visuales y tabla técnica de auditoría de datos.
 * 4. Inspeccionar la ficha técnica y la imagen original en alta resolución de cada carta.
 * 5. Ofrecer acceso directo a "Crear Nueva Carta" y a la "Vista de Jugador" para comprobar
 *    la experiencia del usuario final.
 */

import React, { useState } from "react";
import {
  Check,
  Copy,
  Eye,
  Filter,
  LayoutGrid,
  PlusCircle,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Table as TableIcon,
  X,
} from "lucide-react";
import { AlertBanner } from "../../../../shared/components/AlertBanner";
import { useCardSearch } from "../../../../web_player/modules/catalogo/hooks/useCardSearch";
import {
  useCardImage,
  useCardThumbnail,
} from "../../../../web_player/modules/catalogo/hooks/useCardThumbnail";
import type { CardRarity, CardType, PokemonCard } from "../../../../web_player/modules/catalogo/types/card.types";
import {
  CARD_RARITY_VISUAL_META,
  CARD_TYPE_VISUAL_META,
  formatDisplayPower,
} from "../components/CardPreviewCard";

interface AdminCardThumbnailProps {
  readonly cardId: string;
  readonly cardName: string;
  readonly className?: string;
}

function AdminCardThumbnail({ cardId, cardName, className }: AdminCardThumbnailProps): React.ReactElement {
  const thumbnail = useCardThumbnail(cardId);
  const [hasError, setHasError] = useState(false);

  if (thumbnail && !hasError) {
    return (
      <img
        src={thumbnail}
        alt={cardName}
        className={className}
        onError={() => setHasError(true)}
        loading="lazy"
      />
    );
  }

  return (
    <div className="flex flex-col items-center justify-center p-2 text-center text-slate-500">
      <Sparkles className="w-5 h-5 mb-1 text-slate-600" />
      <span className="text-[10px] text-slate-500 font-mono">Sin miniatura</span>
    </div>
  );
}

function AdminCardDetailImage({ card }: { card: PokemonCard }): React.ReactElement {
  const largeImageUrl = useCardImage(card.id);
  const thumbnailUrl = useCardThumbnail(card.id);
  const [hasError, setHasError] = useState(false);

  const displayUrl = largeImageUrl || thumbnailUrl;

  if (displayUrl && !hasError) {
    return (
      <img
        src={displayUrl}
        alt={card.name}
        className="w-full h-full object-contain drop-shadow-xl"
        onError={() => setHasError(true)}
      />
    );
  }

  return (
    <div className="flex flex-col items-center justify-center p-6 text-center text-slate-500">
      <Sparkles className="w-12 h-12 mb-2 text-slate-600" />
      <span className="text-xs text-slate-400 font-semibold">{card.name}</span>
      <span className="text-[11px] text-slate-600 font-mono">{card.code}</span>
    </div>
  );
}

export interface AdminSearchCardsScreenProps {
  readonly onNavigateToCreate?: () => void;
  readonly onNavigateToPlayerView?: () => void;
}

export function AdminSearchCardsScreen({
  onNavigateToCreate,
  onNavigateToPlayerView,
}: AdminSearchCardsScreenProps): React.ReactElement {
  const {
    searchQuery,
    setSearchQuery,
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
    selectedCost,
    setSelectedCost,
    resetFilters,
  } = useCardSearch({ pageSize: 15 });

  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [inspectedCard, setInspectedCard] = useState<PokemonCard | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleCopy = (text: string, fieldId: string) => {
    void navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const typesList: (CardType | "ALL")[] = ["ALL", "FUE", "AGU", "PLA", "ELE", "PSI", "LUC"];
  const raritiesList: (CardRarity | "ALL")[] = ["ALL", "COMUN", "POCO_COMUN", "RARA", "LEGENDARIA"];
  const costsList: (number | "ALL")[] = ["ALL", 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    selectedType !== "ALL" ||
    selectedRarity !== "ALL" ||
    selectedCost !== "ALL";

  return (
    <div className="w-full text-slate-100 flex flex-col gap-6" data-testid="admin-search-cards-screen">
      {/* --------------------------------------------------------------------- */}
      {/* 1. ENCABEZADO EXCLUSIVO PARA ADMINISTRADORES                          */}
      {/* --------------------------------------------------------------------- */}
      <section className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 rounded-2xl glass-card border border-arena-border p-6 shadow-xl">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/15 text-blue-400">
            <Shield className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
              <span className="text-[11px] font-bold tracking-wider uppercase text-blue-400">
                Panel Administrativo · Control de Catálogo
              </span>
            </div>
            <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
              Buscador y Auditoría de Cartas
            </h1>
            <p className="mt-1 text-xs text-slate-400 max-w-2xl">
              Explora, audita y valida todas las cartas persistidas en la proyección MongoDB y PostgreSQL.
              Esta vista está adaptada para administración técnica global (sin inventario de jugador).
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {onNavigateToCreate && (
            <button
              type="button"
              onClick={onNavigateToCreate}
              className="inline-flex items-center gap-2 rounded-xl bg-arena-accent px-4 py-2.5 text-xs font-bold text-slate-950 shadow-md shadow-amber-500/15 transition hover:bg-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
            >
              <PlusCircle className="h-4 w-4" aria-hidden="true" />
              <span>Crear Nueva Carta</span>
            </button>
          )}

          {onNavigateToPlayerView && (
            <button
              type="button"
              onClick={onNavigateToPlayerView}
              className="inline-flex items-center gap-2 rounded-xl border border-blue-500/30 bg-blue-950/40 px-3.5 py-2.5 text-xs font-semibold text-blue-200 transition hover:bg-blue-900/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              title="Abre la pestaña de vista de jugador para confirmar cómo se visualizan las cartas en el catálogo y colección del jugador"
            >
              <Eye className="h-4 w-4 text-blue-400" aria-hidden="true" />
              <span>Vista de Jugador</span>
            </button>
          )}
        </div>
      </section>

      {/* --------------------------------------------------------------------- */}
      {/* 2. BARRA DE BÚSQUEDA Y FILTROS ADMINISTRATIVOS                        */}
      {/* --------------------------------------------------------------------- */}
      <section className="rounded-2xl border border-arena-border bg-arena-card/85 p-5 shadow-lg space-y-4">
        {/* Fila superior: Input de búsqueda + Modos de vista + Recargar */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          <form
            onSubmit={handleSearch}
            className="flex-1 relative flex items-center"
          >
            <Search className="absolute left-3.5 h-4 w-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar por nombre, código oficial (PKA-...) o descripción..."
              className="w-full rounded-xl border border-arena-border bg-arena-surface/80 pl-10 pr-24 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition focus:border-blue-400 focus:bg-arena-surface focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute right-14 text-slate-400 hover:text-slate-200 p-1"
                aria-label="Limpiar texto"
              >
                <X className="h-4 w-4" />
              </button>
            )}
            <button
              type="submit"
              disabled={isLoading}
              className="absolute right-2 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white transition hover:bg-blue-500 disabled:opacity-50"
            >
              Buscar
            </button>
          </form>

          {/* Selector de modo: Grilla vs Tabla */}
          <div className="flex items-center gap-1.5 rounded-xl border border-arena-border bg-arena-surface p-1 shrink-0 self-end md:self-auto">
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                viewMode === "grid"
                  ? "bg-blue-600 text-white shadow"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
              title="Vista en tarjetas"
            >
              <LayoutGrid className="h-4 w-4" />
              <span className="hidden sm:inline">Tarjetas</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                viewMode === "table"
                  ? "bg-blue-600 text-white shadow"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
              title="Vista en tabla técnica"
            >
              <TableIcon className="h-4 w-4" />
              <span className="hidden sm:inline">Tabla</span>
            </button>
            <button
              type="button"
              onClick={reload}
              disabled={isLoading}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
              title="Recargar catálogo desde MongoDB"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin text-blue-400" : ""}`} />
            </button>
          </div>
        </div>

        {/* Fila de chips de filtros: Tipo, Rareza, Costo */}
        <div className="flex flex-col gap-3 pt-2 border-t border-arena-border/50 text-xs">
          {/* Filtro por Tipo */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
              Tipo:
            </span>
            {typesList.map((type) => {
              const isSelected = selectedType === type;
              const meta = type !== "ALL" ? CARD_TYPE_VISUAL_META[type] : null;
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => setSelectedType(type)}
                  className={`px-2.5 py-1 rounded-lg border font-medium transition flex items-center gap-1 ${
                    isSelected
                      ? "border-blue-400 bg-blue-500/20 text-blue-200 font-bold shadow-sm"
                      : "border-arena-border bg-arena-surface/60 text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  {meta && <meta.Icon className="h-3 w-3" />}
                  <span>{type === "ALL" ? "Todos los tipos" : meta?.label ?? type}</span>
                </button>
              );
            })}
          </div>

          {/* Filtro por Rareza */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
              Rareza:
            </span>
            {raritiesList.map((rarity) => {
              const isSelected = selectedRarity === rarity;
              const meta = rarity !== "ALL" ? CARD_RARITY_VISUAL_META[rarity] : null;
              return (
                <button
                  key={rarity}
                  type="button"
                  onClick={() => setSelectedRarity(rarity)}
                  className={`px-2.5 py-1 rounded-lg border font-medium transition ${
                    isSelected
                      ? "border-amber-400 bg-amber-500/20 text-amber-200 font-bold shadow-sm"
                      : "border-arena-border bg-arena-surface/60 text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  {rarity === "ALL" ? "Todas las rarezas" : meta?.label ?? rarity}
                </button>
              );
            })}
          </div>

          {/* Filtro por Costo */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
              Costo:
            </span>
            {costsList.map((cost) => {
              const isSelected = selectedCost === cost;
              return (
                <button
                  key={String(cost)}
                  type="button"
                  onClick={() => setSelectedCost(cost)}
                  className={`px-2.5 py-1 rounded-lg border font-mono font-medium transition ${
                    isSelected
                      ? "border-emerald-400 bg-emerald-500/20 text-emerald-200 font-bold shadow-sm"
                      : "border-arena-border bg-arena-surface/60 text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  {cost === "ALL" ? "Todos los costos" : `⚡ ${cost}`}
                </button>
              );
            })}

            {hasActiveFilters && (
              <button
                type="button"
                onClick={resetFilters}
                className="ml-auto text-xs text-red-400 hover:text-red-300 underline font-medium flex items-center gap-1 py-1"
              >
                <X className="h-3 w-3" />
                <span>Limpiar filtros</span>
              </button>
            )}
          </div>
        </div>

        {/* Resumen de resultados */}
        <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-arena-border/30">
          <div>
            Total registradas: <strong className="text-white font-mono">{totalResults}</strong>
            {totalResults > 0 && (
              <span> · Mostrando página <strong className="text-white">{currentPage}</strong> de <strong className="text-white">{totalPages}</strong></span>
            )}
          </div>
          <div className="text-[11px] text-slate-500">
            Fuente autoritativa: MongoDB <code className="text-slate-400">cards_projection</code>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------------- */}
      {/* 3. ALERTAS DE ERROR / INDISPONIBILIDAD                                */}
      {/* --------------------------------------------------------------------- */}
      {isCatalogUnavailable && (
        <AlertBanner
          variant="error"
          title="Catálogo no disponible (503)"
          description="No fue posible conectar con la proyección NoSQL en MongoDB. Verifica que los servicios de base de datos estén activos."
          actionLabel="Reintentar conexión"
          onAction={reload}
        />
      )}

      {error && !isCatalogUnavailable && (
        <AlertBanner
          variant="error"
          title="Error en la consulta"
          description={error}
          actionLabel="Reintentar"
          onAction={reload}
        />
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 4. RESULTADOS: MODO GRILLA O MODO TABLA                               */}
      {/* --------------------------------------------------------------------- */}
      {isLoading ? (
        <div className="rounded-2xl border border-arena-border bg-arena-card/60 p-12 text-center space-y-4">
          <RefreshCw className="h-8 w-8 animate-spin text-blue-400 mx-auto" />
          <p className="text-sm font-semibold text-slate-200">Consultando catálogo oficial...</p>
        </div>
      ) : results.length === 0 ? (
        <div className="rounded-2xl border border-arena-border bg-arena-card/70 p-12 text-center space-y-4">
          <div className="h-12 w-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
            <Filter className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">No se encontraron cartas</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
              Ninguna carta coincide con los criterios de búsqueda y filtros seleccionados.
            </p>
          </div>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex items-center gap-1.5 rounded-xl border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-xs font-semibold text-blue-300 hover:bg-blue-500/20 transition"
            >
              <span>Restablecer filtros de búsqueda</span>
            </button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        /* VISTA DE TARJETAS / GRILLA */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {results.map((card) => {
            const cardType = (card.type || "FUE") as CardType;
            const cardRarity = (card.rarity || "COMUN") as CardRarity;
            const typeMeta = CARD_TYPE_VISUAL_META[cardType] ?? CARD_TYPE_VISUAL_META.FUE;
            const rarityMeta = CARD_RARITY_VISUAL_META[cardRarity] ?? CARD_RARITY_VISUAL_META.COMUN;
            const { Icon: TypeIcon } = typeMeta;

            return (
              <article
                key={card.id}
                className="rounded-2xl border border-arena-border bg-arena-card/90 p-4 shadow-lg flex flex-col justify-between hover:border-blue-500/50 transition-all group"
              >
                <div>
                  {/* Imagen y badges superiores */}
                  <div className="relative aspect-[5/3.5] rounded-xl overflow-hidden bg-slate-950 border border-arena-border/60 mb-3.5 flex items-center justify-center">
                    <AdminCardThumbnail
                      cardId={card.id}
                      cardName={card.name}
                      className="w-full h-full object-contain p-1 group-hover:scale-105 transition-transform duration-300"
                    />
                    <div className="absolute top-2 left-2 flex items-center gap-1.5 pointer-events-none">
                      <span className="px-2 py-0.5 rounded bg-slate-900/90 border border-slate-700 font-mono text-[11px] font-extrabold text-emerald-300">
                        {card.code}
                      </span>
                    </div>
                    <div className="absolute top-2 right-2 flex items-center gap-1 pointer-events-none">
                      <span className="px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-500/40 text-[10px] font-mono font-bold text-amber-300">
                        ⚡ {card.cost}
                      </span>
                    </div>
                  </div>

                  {/* Nombre y tipo */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="text-base font-bold text-white group-hover:text-blue-300 transition-colors truncate">
                      {card.name}
                    </h3>
                    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase shrink-0 ${typeMeta.badgeClass}`}>
                      <TypeIcon className="h-3 w-3" />
                      {card.type}
                    </span>
                  </div>

                  {/* Estadísticas técnicas */}
                  <div className="grid grid-cols-2 gap-2 text-xs bg-arena-surface/60 rounded-xl p-2.5 border border-arena-border/50 mb-3">
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Poder / HP</span>
                      <span className="font-mono font-bold text-slate-200">
                        ⚔️ {formatDisplayPower(card.power)} · ❤️ {card.hp}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Rareza</span>
                      <span className="text-[10px] font-bold uppercase text-slate-300">
                        {rarityMeta.label}
                      </span>
                    </div>
                    {card.ability_name && (
                      <div className="col-span-2 truncate">
                        <span className="text-[10px] text-slate-400 block uppercase">Habilidad</span>
                        <span className="text-[11px] font-semibold text-slate-200 truncate">
                          <span className="font-mono text-blue-300">{card.ability_code}</span> — {card.ability_name}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Botón de inspección */}
                <button
                  type="button"
                  onClick={() => setInspectedCard(card)}
                  className="w-full mt-2 inline-flex items-center justify-center gap-1.5 rounded-xl border border-blue-500/40 bg-blue-950/40 px-3 py-2 text-xs font-semibold text-blue-200 hover:bg-blue-900/60 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <Eye className="h-3.5 w-3.5 text-blue-400" />
                  <span>Ver Ficha & Medios Originales</span>
                </button>
              </article>
            );
          })}
        </div>
      ) : (
        /* VISTA DE TABLA TÉCNICA */
        <div className="rounded-2xl border border-arena-border bg-arena-card/90 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-arena-border bg-arena-surface/80 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="py-3 px-4">Código</th>
                  <th className="py-3 px-3">Miniatura</th>
                  <th className="py-3 px-4">Nombre</th>
                  <th className="py-3 px-3">Tipo</th>
                  <th className="py-3 px-3">Rareza</th>
                  <th className="py-3 px-3">Costo</th>
                  <th className="py-3 px-3">Poder / HP</th>
                  <th className="py-3 px-4">Habilidad</th>
                  <th className="py-3 px-4">ID Sistema</th>
                  <th className="py-3 px-4 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-arena-border/50 text-slate-200">
                {results.map((card) => {
                  const cardType = (card.type || "FUE") as CardType;
                  const typeMeta = CARD_TYPE_VISUAL_META[cardType] ?? CARD_TYPE_VISUAL_META.FUE;
                  const { Icon: TypeIcon } = typeMeta;

                  return (
                    <tr key={card.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 px-4 font-mono font-extrabold text-emerald-300">
                        {card.code}
                      </td>
                      <td className="py-2 px-3">
                        <div className="h-10 w-10 rounded-lg overflow-hidden bg-slate-950 border border-arena-border/60 flex items-center justify-center shrink-0">
                          <AdminCardThumbnail cardId={card.id} cardName={card.name} className="h-full w-full object-contain p-0.5" />
                        </div>
                      </td>
                      <td className="py-3 px-4 font-bold text-white max-w-[180px] truncate">
                        {card.name}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${typeMeta.badgeClass}`}>
                          <TypeIcon className="h-2.5 w-2.5" />
                          {card.type}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-[10px] font-semibold text-slate-300 uppercase">
                          {card.rarity}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono font-bold text-amber-300">
                        ⚡ {card.cost}
                      </td>
                      <td className="py-3 px-3 font-mono">
                        {card.power} / {card.hp}
                      </td>
                      <td className="py-3 px-4 max-w-[180px] truncate text-slate-300">
                        {card.ability_name ? `${card.ability_code} · ${card.ability_name}` : "—"}
                      </td>
                      <td className="py-3 px-4 font-mono text-[10px] text-slate-400 select-all max-w-[120px] truncate">
                        {card.id}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => setInspectedCard(card)}
                          className="inline-flex items-center gap-1 rounded-lg border border-blue-500/40 bg-blue-500/15 px-2.5 py-1 text-[11px] font-semibold text-blue-300 hover:bg-blue-500/25 transition"
                        >
                          <Eye className="h-3 w-3" />
                          <span>Ficha</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 5. CONTROLES DE PAGINACIÓN DE SERVIDOR                                */}
      {/* --------------------------------------------------------------------- */}
      {totalPages > 1 && (
        <section className="flex flex-col sm:flex-row items-center justify-between gap-4 py-2 border-t border-arena-border/50">
          <div className="text-xs text-slate-400">
            Página <strong className="text-white">{currentPage}</strong> de <strong className="text-white">{totalPages}</strong> (15 cartas por página)
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={prevPage}
              disabled={currentPage <= 1 || isLoading}
              className="rounded-xl border border-arena-border bg-arena-card px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition"
            >
              Anterior
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNumber = i + 1;
                if (totalPages > 5 && currentPage > 3) {
                  pageNumber = currentPage - 3 + i;
                  if (pageNumber > totalPages) pageNumber = totalPages - (4 - i);
                }
                return (
                  <button
                    key={pageNumber}
                    type="button"
                    onClick={() => goToPage(pageNumber)}
                    className={`h-8 w-8 rounded-lg text-xs font-bold transition ${
                      currentPage === pageNumber
                        ? "bg-blue-600 text-white shadow"
                        : "border border-arena-border bg-arena-card text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    {pageNumber}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              onClick={nextPage}
              disabled={currentPage >= totalPages || isLoading}
              className="rounded-xl border border-arena-border bg-arena-card px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition"
            >
              Siguiente
            </button>
          </div>
        </section>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 6. MODAL DE INSPECCIÓN TÉCNICA ADMINISTRATIVA (IMAGEN ORIGINAL & IDS) */}
      {/* --------------------------------------------------------------------- */}
      {inspectedCard && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setInspectedCard(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-admin-title"
        >
          <div
            className="relative w-full max-w-3xl rounded-2xl border border-arena-border bg-arena-card p-6 shadow-2xl flex flex-col md:flex-row gap-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Botón cerrar */}
            <button
              type="button"
              onClick={() => setInspectedCard(null)}
              className="absolute top-4 right-4 rounded-xl border border-arena-border bg-arena-surface p-2 text-slate-400 hover:text-white hover:bg-slate-800 transition"
              aria-label="Cerrar modal"
            >
              <X className="h-5 w-5" />
            </button>

            {/* Columna izquierda: Imagen Grande / Original */}
            <div className="w-full md:w-5/12 flex flex-col items-center">
              <div className="w-full aspect-[5/7] rounded-xl overflow-hidden bg-slate-950 border border-arena-border shadow-inner flex items-center justify-center p-2 relative group">
                <AdminCardDetailImage card={inspectedCard} />
              </div>
              <div className="w-full mt-3 flex items-center justify-between text-[11px] text-slate-400">
                <span>Versión Grande (GridFS)</span>
                <span className="font-mono text-[10px] text-slate-500">{inspectedCard.code}</span>
              </div>
            </div>

            {/* Columna derecha: Atributos Técnicos e IDs del Sistema */}
            <div className="w-full md:w-7/12 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="px-2.5 py-0.5 rounded-md bg-emerald-950/80 border border-emerald-500/50 font-mono text-sm font-extrabold text-emerald-300">
                    {inspectedCard.code}
                  </span>
                  <span className="px-2 py-0.5 rounded-md bg-blue-950/80 border border-blue-500/40 text-[11px] font-bold text-blue-300 uppercase">
                    {inspectedCard.type}
                  </span>
                  <span className="px-2 py-0.5 rounded-md bg-amber-950/80 border border-amber-500/40 text-[11px] font-bold text-amber-300 uppercase">
                    {inspectedCard.rarity}
                  </span>
                </div>

                <h2 id="modal-admin-title" className="text-2xl font-black text-white">
                  {inspectedCard.name}
                </h2>

                <p className="mt-2 text-xs text-slate-300 leading-relaxed bg-arena-surface/50 p-3 rounded-xl border border-arena-border/50">
                  {inspectedCard.description || "Sin descripción adicional registrada."}
                </p>

                {/* Métricas de combate */}
                <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                  <div className="rounded-xl border border-arena-border bg-arena-surface p-2.5">
                    <span className="text-[10px] text-slate-400 block uppercase font-bold">Costo</span>
                    <span className="text-base font-mono font-extrabold text-amber-300">⚡ {inspectedCard.cost}</span>
                  </div>
                  <div className="rounded-xl border border-arena-border bg-arena-surface p-2.5">
                    <span className="text-[10px] text-slate-400 block uppercase font-bold">Poder</span>
                    <span className="text-base font-mono font-extrabold text-blue-300">⚔️ {inspectedCard.power}</span>
                  </div>
                  <div className="rounded-xl border border-arena-border bg-arena-surface p-2.5">
                    <span className="text-[10px] text-slate-400 block uppercase font-bold">Puntos Vida</span>
                    <span className="text-base font-mono font-extrabold text-emerald-300">❤️ {inspectedCard.hp}</span>
                  </div>
                </div>

                {/* Habilidad */}
                {inspectedCard.ability_name && (
                  <div className="mt-4 rounded-xl border border-blue-500/30 bg-blue-950/20 p-3 text-xs">
                    <span className="text-[10px] text-blue-400 uppercase font-bold block mb-0.5">
                      Habilidad Asociada
                    </span>
                    <span className="font-bold text-white">
                      <span className="font-mono text-blue-300">{inspectedCard.ability_code}</span> — {inspectedCard.ability_name}
                    </span>
                  </div>
                )}

                {/* Metadatos de Sistema */}
                <div className="mt-4 space-y-2 text-xs">
                  <div className="flex items-center justify-between rounded-lg bg-slate-900/80 px-3 py-2 border border-arena-border/60">
                    <span className="text-[11px] text-slate-400">ID Primario (PostgreSQL/Mongo):</span>
                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-200">
                      <span className="select-all">{inspectedCard.id}</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(inspectedCard.id, "card-id")}
                        className="text-slate-400 hover:text-white"
                        title="Copiar ID"
                      >
                        {copiedField === "card-id" ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between rounded-lg bg-slate-900/80 px-3 py-2 border border-arena-border/60">
                    <span className="text-[11px] text-slate-400">Código Oficial Canónico:</span>
                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-emerald-300 font-bold">
                      <span className="select-all">{inspectedCard.code}</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(inspectedCard.code, "card-code")}
                        className="text-slate-400 hover:text-white"
                        title="Copiar Código"
                      >
                        {copiedField === "card-code" ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Pie del modal */}
              <div className="pt-4 border-t border-arena-border flex items-center justify-end">
                <button
                  type="button"
                  onClick={() => setInspectedCard(null)}
                  className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition"
                >
                  Cerrar Ficha
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
