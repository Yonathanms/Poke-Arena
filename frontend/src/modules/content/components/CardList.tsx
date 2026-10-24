import React, { useEffect, useState, useCallback } from "react";
import { Search, RotateCcw, Sparkles } from "lucide-react";
import { apiFetch } from "@/shared/api/client";
import { CardDTO, CardType, SearchCardsResponseDTO } from "../types/content";
import { CardItem } from "./CardItem";

export const CardList: React.FC = () => {
  const [cards, setCards] = useState<CardDTO[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [nameQuery, setNameQuery] = useState<string>("");
  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedCost, setSelectedCost] = useState<string>("");
  const [selectedRarity, setSelectedRarity] = useState<string>("");

  const fetchCards = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (nameQuery.trim()) params.set("name", nameQuery.trim());
      if (selectedType) params.set("card_type", selectedType);
      if (selectedCost) params.set("cost", selectedCost);
      if (selectedRarity) params.set("rarity", selectedRarity);

      const endpoint = `/content/cards?${params.toString()}`;
      const data = await apiFetch<SearchCardsResponseDTO>(endpoint);
      setCards(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Error al buscar cartas:", err);
      setCards([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [nameQuery, selectedType, selectedCost, selectedRarity]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCards();
    }, 300);
    return () => clearTimeout(timer);
  }, [fetchCards]);

  const handleResetFilters = () => {
    setNameQuery("");
    setSelectedType("");
    setSelectedCost("");
    setSelectedRarity("");
  };

  const types: CardType[] = ["FUE", "AGU", "PLA", "ELE", "PSI", "LUC"];
  const costs = [1, 2, 3, 4, 5, 6];

  return (
    <div className="space-y-6">
      {/* Search & Filter Bar */}
      <div className="glass-panel p-5 rounded-2xl border border-arena-border shadow-xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
          {/* Name search */}
          <div className="relative lg:col-span-2">
            <Search className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Buscar por nombre (ej: Charmander)..."
              value={nameQuery}
              onChange={(e) => setNameQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
          </div>

          {/* Type filter */}
          <div>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">Todos los tipos</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  Tipo {t}
                </option>
              ))}
            </select>
          </div>

          {/* Cost filter */}
          <div>
            <select
              value={selectedCost}
              onChange={(e) => setSelectedCost(e.target.value)}
              className="w-full px-3 py-2 bg-arena-surface border border-arena-border rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">Cualquier costo</option>
              {costs.map((c) => (
                <option key={c} value={c}>
                  Costo: {c} Energía
                </option>
              ))}
            </select>
          </div>

          {/* Rarity filter or Reset */}
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

            {(nameQuery || selectedType || selectedCost || selectedRarity) && (
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

        {/* Counter */}
        <div className="mt-3.5 flex items-center justify-between text-xs text-slate-400">
          <span>Mostrando {cards.length} cartas de {total} en catálogo</span>
          <span className="flex items-center gap-1 text-blue-400 font-medium">
            <Sparkles className="w-3.5 h-3.5" /> Consultas rápidas en MongoDB (US 2.1.2)
          </span>
        </div>
      </div>

      {/* Grid of Cards */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="aspect-[5/7] rounded-2xl bg-arena-surface/40 animate-pulse border border-arena-border/40" />
          ))}
        </div>
      ) : cards.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-2xl border border-arena-border">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400">
            <Search className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-slate-200">No se encontraron cartas</h3>
          <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
            Intenta ajustar los filtros de búsqueda o crea tu primera carta desde la pestaña "Crear Carta".
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {cards.map((card) => (
            <CardItem key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
};
