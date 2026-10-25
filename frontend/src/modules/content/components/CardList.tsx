import React, { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Lock, RotateCcw, Search, Sparkles } from "lucide-react";
import { apiFetch, ApiClientError } from "@/shared/api/client";
import { CardDTO, CardType, SearchCardsResponseDTO } from "../types/content";
import { CardItem } from "./CardItem";

interface CardListProps {
  isAuthenticated: boolean;
}

export const CardList: React.FC<CardListProps> = ({ isAuthenticated }) => {
  const [cards, setCards] = useState<CardDTO[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [authError, setAuthError] = useState<boolean>(false);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // Filtros básicos
  const [nameQuery, setNameQuery] = useState<string>("");
  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedCost, setSelectedCost] = useState<string>("");
  const [selectedRarity, setSelectedRarity] = useState<string>("");

  // Filtros avanzados
  const [codeQuery, setCodeQuery] = useState<string>("");
  const [costMin, setCostMin] = useState<string>("");
  const [costMax, setCostMax] = useState<string>("");
  const [powerExact, setPowerExact] = useState<string>("");
  const [powerMin, setPowerMin] = useState<string>("");
  const [powerMax, setPowerMax] = useState<string>("");
  const [abilityCode, setAbilityCode] = useState<string>("");

  const hasAdvancedFilters =
    codeQuery || costMin || costMax || powerExact || powerMin || powerMax || abilityCode;

  const fetchCards = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setAuthError(false);
    try {
      const params = new URLSearchParams();
      if (nameQuery.trim()) params.set("name", nameQuery.trim());
      if (codeQuery.trim()) params.set("code", codeQuery.trim());
      if (selectedType) params.set("card_type", selectedType);
      if (selectedRarity) params.set("rarity", selectedRarity);

      // cost: usar rango si está definido, exacto si no
      if (costMin || costMax) {
        if (costMin) params.set("cost_min", costMin);
        if (costMax) params.set("cost_max", costMax);
      } else if (selectedCost) {
        params.set("cost", selectedCost);
      }

      // power: usar rango si está definido, exacto si no
      if (powerMin || powerMax) {
        if (powerMin) params.set("power_min", powerMin);
        if (powerMax) params.set("power_max", powerMax);
      } else if (powerExact !== "") {
        params.set("power", powerExact);
      }

      if (abilityCode.trim()) params.set("ability_code", abilityCode.trim());

      const data = await apiFetch<SearchCardsResponseDTO>(`/content/cards?${params.toString()}`);
      setCards(data.items);
      setTotal(data.total);
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 401 || err.status === 403)) {
        setAuthError(true);
      }
      setCards([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [
    isAuthenticated,
    nameQuery,
    codeQuery,
    selectedType,
    selectedCost,
    selectedRarity,
    costMin,
    costMax,
    powerExact,
    powerMin,
    powerMax,
    abilityCode,
  ]);

  useEffect(() => {
    if (!isAuthenticated) {
      setCards([]);
      setTotal(0);
      setAuthError(false);
      return;
    }
    const timer = setTimeout(() => void fetchCards(), 300);
    return () => clearTimeout(timer);
  }, [fetchCards, isAuthenticated]);

  const handleResetFilters = () => {
    setNameQuery("");
    setCodeQuery("");
    setSelectedType("");
    setSelectedCost("");
    setSelectedRarity("");
    setCostMin("");
    setCostMax("");
    setPowerExact("");
    setPowerMin("");
    setPowerMax("");
    setAbilityCode("");
  };

  const hasAnyFilter =
    nameQuery || codeQuery || selectedType || selectedCost || selectedRarity || hasAdvancedFilters;

  const types: CardType[] = ["FUE", "AGU", "PLA", "ELE", "PSI", "LUC"];

  // Panel de "requiere login"
  if (!isAuthenticated) {
    return (
      <div className="glass-panel p-12 text-center rounded-2xl border border-amber-500/30">
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-amber-500/10 flex items-center justify-center text-amber-400">
          <Lock className="w-7 h-7" />
        </div>
        <h3 className="text-base font-semibold text-slate-200">Inicia sesión para ver el catálogo</h3>
        <p className="text-sm text-slate-400 mt-2 max-w-sm mx-auto">
          Buscar cartas requiere una sesión de administrador. Usa el botón{" "}
          <span className="text-emerald-400 font-medium">Entrar como admin local</span> en la barra superior.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Panel de filtros */}
      <div className="glass-panel p-5 rounded-2xl border border-arena-border shadow-xl space-y-3.5">

        {/* Fila básica */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
          {/* Nombre */}
          <div className="relative lg:col-span-2">
            <Search className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Nombre (ej: Charmand, pokemon…)"
              value={nameQuery}
              onChange={(e) => setNameQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
          </div>

          {/* Tipo */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">Todos los tipos</option>
            {types.map((t) => (
              <option key={t} value={t}>Tipo {t}</option>
            ))}
          </select>

          {/* Costo exacto — se deshabilita si hay rango */}
          <select
            value={costMin || costMax ? "" : selectedCost}
            onChange={(e) => { setSelectedCost(e.target.value); setCostMin(""); setCostMax(""); }}
            disabled={!!(costMin || costMax)}
            className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500 disabled:opacity-40"
            title={costMin || costMax ? "Limpia el rango de costo para usar costo exacto" : undefined}
          >
            <option value="">Cualquier costo</option>
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((c) => (
              <option key={c} value={c}>Costo: {c}</option>
            ))}
          </select>

          {/* Rareza + Reset */}
          <div className="flex items-center gap-2">
            <select
              value={selectedRarity}
              onChange={(e) => setSelectedRarity(e.target.value)}
              className="flex-1 px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">Rarezas</option>
              <option value="COMUN">Común</option>
              <option value="POCO_COMUN">Poco común</option>
              <option value="RARA">Rara</option>
              <option value="LEGENDARIA">Legendaria</option>
            </select>
            {hasAnyFilter && (
              <button
                onClick={handleResetFilters}
                title="Limpiar filtros"
                className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Botón toggle filtros avanzados */}
        <button
          onClick={() => setShowAdvanced((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium"
        >
          {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          {showAdvanced ? "Ocultar filtros avanzados" : "Filtros avanzados"}
          {hasAdvancedFilters && !showAdvanced && (
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 text-[10px]">
              activos
            </span>
          )}
        </button>

        {/* Sección de filtros avanzados */}
        {showAdvanced && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 pt-1 border-t border-arena-border/50">
            {/* Código exacto */}
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Código exacto</label>
              <input
                type="text"
                placeholder="ej: PKA-FUE-001"
                value={codeQuery}
                onChange={(e) => setCodeQuery(e.target.value)}
                className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Rango de costo */}
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">
                Rango de costo{" "}
                {selectedCost && !costMin && !costMax && (
                  <span className="text-amber-400">(limpia costo exacto al activar)</span>
                )}
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="Mín"
                  min={0}
                  max={10}
                  value={costMin}
                  onChange={(e) => { setCostMin(e.target.value); setSelectedCost(""); }}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
                <span className="text-slate-500 text-xs">–</span>
                <input
                  type="number"
                  placeholder="Máx"
                  min={0}
                  max={10}
                  value={costMax}
                  onChange={(e) => { setCostMax(e.target.value); setSelectedCost(""); }}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Poder exacto */}
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Poder exacto</label>
              <input
                type="number"
                placeholder="ej: 5"
                min={-20}
                max={20}
                value={powerExact}
                onChange={(e) => { setPowerExact(e.target.value); setPowerMin(""); setPowerMax(""); }}
                disabled={!!(powerMin || powerMax)}
                className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-40"
              />
            </div>

            {/* Rango de poder */}
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Rango de poder</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="Mín"
                  min={-20}
                  max={20}
                  value={powerMin}
                  onChange={(e) => { setPowerMin(e.target.value); setPowerExact(""); }}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
                <span className="text-slate-500 text-xs">–</span>
                <input
                  type="number"
                  placeholder="Máx"
                  min={-20}
                  max={20}
                  value={powerMax}
                  onChange={(e) => { setPowerMax(e.target.value); setPowerExact(""); }}
                  className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Habilidad */}
            <div className="sm:col-span-2 lg:col-span-4">
              <label className="block text-[11px] text-slate-400 mb-1">Código de habilidad</label>
              <input
                type="text"
                placeholder="ej: HAB-001 o HAB-000 para Sin habilidad"
                value={abilityCode}
                onChange={(e) => setAbilityCode(e.target.value)}
                className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
        )}

        {/* Contador */}
        <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
          <span>
            {authError
              ? "⚠️ Sin autorización para ver el catálogo"
              : `Mostrando ${cards.length} cartas de ${total} en catálogo`}
          </span>
          <span className="flex items-center gap-1 text-blue-400 font-medium">
            <Sparkles className="w-3.5 h-3.5" /> Consultas rápidas en MongoDB (US 2.1.2)
          </span>
        </div>
      </div>

      {/* Error de autorización */}
      {authError && (
        <div className="glass-panel p-8 text-center rounded-2xl border border-red-500/30">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-red-500/10 flex items-center justify-center text-red-400">
            <Lock className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-slate-200">Sin autorización</h3>
          <p className="text-sm text-slate-400 mt-1">
            La sesión activa no tiene permisos para consultar el catálogo.
          </p>
        </div>
      )}

      {/* Grid de cartas */}
      {!authError && (
        loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {[...Array(10)].map((_, i) => (
              <div
                key={i}
                className="aspect-[5/7] rounded-2xl bg-arena-surface/40 animate-pulse border border-arena-border/40"
              />
            ))}
          </div>
        ) : cards.length === 0 ? (
          <div className="glass-panel p-12 text-center rounded-2xl border border-arena-border">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400">
              <Search className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-200">No se encontraron cartas</h3>
            <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
              Ajusta los filtros de búsqueda o crea tu primera carta desde la pestaña "Crear Carta".
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {cards.map((card) => (
              <CardItem key={card.id} card={card} />
            ))}
          </div>
        )
      )}
    </div>
  );
};
