/**
 * Hook React para búsqueda, filtrado y paginación en el Catálogo de Cartas (`useCardSearch.ts`).
 *
 * Responsabilidades:
 * 1. Conectar con el catálogo real de MongoDB mediante `searchCards` (`GET /api/v1/content/cards`).
 * 2. Eliminar completamente el uso de datos mock en producción.
 * 3. Gestionar filtros de texto (`q`), tipo canónico (`tipo`) y rareza canónica (`rareza`).
 * 4. Controlar la paginación de servidor (`pagina`, `limite`, `total_paginas`, `total`).
 * 5. Prevenir condiciones de carrera (out-of-order) descartando respuestas desfasadas.
 * 6. Identificar y reportar específicamente el estado `503 catalogo_no_disponible` con opción de recarga.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { searchCards, type CardApiRequestOptions } from "../services/cards.api";
import type { CardRarity, CardType, PokemonCard } from "../types/card.types";

export interface UseCardSearchOptions extends CardApiRequestOptions {
  readonly initialQuery?: string;
  readonly initialType?: CardType | "ALL";
  readonly initialRarity?: CardRarity | "ALL";
  readonly initialCost?: number | "ALL";
  readonly initialOnlyOwned?: boolean;
  readonly pageSize?: number;
  readonly autoLoad?: boolean;
}

export interface UseCardSearchResult {
  readonly searchQuery: string;
  readonly setSearchQuery: (query: string) => void;
  readonly hasSearched: boolean;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly isCatalogUnavailable: boolean;
  readonly results: PokemonCard[];
  readonly totalResults: number;
  readonly currentPage: number;
  readonly totalPages: number;
  readonly pageSize: number;
  readonly handleSearch: (e?: React.FormEvent) => void;
  readonly handleClear: () => void;
  readonly goToPage: (page: number) => void;
  readonly nextPage: () => void;
  readonly prevPage: () => void;
  readonly reload: () => void;
  readonly selectedType: CardType | "ALL";
  readonly setSelectedType: (type: CardType | "ALL") => void;
  readonly selectedRarity: CardRarity | "ALL";
  readonly setSelectedRarity: (rarity: CardRarity | "ALL") => void;
  readonly selectedCost: number | "ALL";
  readonly setSelectedCost: (cost: number | "ALL") => void;
  readonly onlyOwned: boolean;
  readonly setOnlyOwned: (onlyOwned: boolean) => void;
  readonly resetFilters: () => void;
}

const DEFAULT_PAGE_SIZE = 15;

export function useCardSearch(
  optionsOrQuery: string | UseCardSearchOptions = ""
): UseCardSearchResult {
  const options: UseCardSearchOptions =
    typeof optionsOrQuery === "string"
      ? { initialQuery: optionsOrQuery }
      : optionsOrQuery;

  const pageSize = options.pageSize ?? DEFAULT_PAGE_SIZE;
  const autoLoad = options.autoLoad ?? true;

  const [searchQuery, setSearchQuery] = useState(options.initialQuery ?? "");
  const [selectedType, setSelectedTypeState] = useState<CardType | "ALL">(
    options.initialType ?? "ALL"
  );
  const [selectedRarity, setSelectedRarityState] = useState<CardRarity | "ALL">(
    options.initialRarity ?? "ALL"
  );
  const [selectedCost, setSelectedCostState] = useState<number | "ALL">(
    options.initialCost ?? "ALL"
  );
  const [onlyOwned, setOnlyOwnedState] = useState<boolean>(
    options.initialOnlyOwned ?? false
  );
  const [currentPage, setCurrentPage] = useState(1);

  const [hasSearched, setHasSearched] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCatalogUnavailable, setIsCatalogUnavailable] = useState(false);
  const [results, setResults] = useState<PokemonCard[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Contador monotónico para resolver peticiones desordenadas
  const requestIdRef = useRef(0);

  // Ejecuta la búsqueda contra el backend
  const executeFetch = useCallback(
    async (
      queryText: string,
      typeFilter: CardType | "ALL",
      rarityFilter: CardRarity | "ALL",
      costFilter: number | "ALL",
      ownedOnly: boolean,
      page: number
    ) => {
      const currentRequestId = ++requestIdRef.current;
      setIsLoading(true);
      setError(null);
      setIsCatalogUnavailable(false);

      try {
        const response = await searchCards(
          {
            q: queryText.trim().length > 0 ? queryText.trim() : null,
            tipo: typeFilter !== "ALL" ? typeFilter : null,
            rareza: rarityFilter !== "ALL" ? rarityFilter : null,
            costo: costFilter !== "ALL" ? costFilter : null,
            solo_propias: ownedOnly ? true : undefined,
            pagina: page,
            limite: pageSize,
          },
          {
            fetchImpl: options.fetchImpl,
            baseUrl: options.baseUrl,
          }
        );

        // Si llegó una respuesta de una petición más antigua, descartarla
        if (currentRequestId !== requestIdRef.current) {
          return;
        }

        setResults(response.data.items);
        setTotalResults(response.data.total);
        setCurrentPage(response.data.pagina);
        setTotalPages(Math.max(1, response.data.total_paginas));
        setHasSearched(true);
      } catch (err: unknown) {
        if (currentRequestId !== requestIdRef.current) {
          return;
        }

        if (err instanceof ApiHttpError) {
          if (err.status === 503) {
            setIsCatalogUnavailable(true);
            setError(
              err.detail || "Catálogo no disponible. No fue posible conectar con la base de datos."
            );
          } else if (err.status === 401) {
            setError("Sesión expirada o no autorizada. Inicia sesión nuevamente.");
          } else {
            setError(err.detail || `Error al consultar el catálogo (${err.status}).`);
          }
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Error inesperado al conectar con el servidor.");
        }

        setResults([]);
        setTotalResults(0);
        setTotalPages(1);
        setHasSearched(true);
      } finally {
        if (currentRequestId === requestIdRef.current) {
          setIsLoading(false);
        }
      }
    },
    [pageSize, options.fetchImpl, options.baseUrl]
  );

  // Manejador de envío manual del formulario
  const handleSearch = useCallback(
    (e?: React.FormEvent) => {
      if (e) {
        e.preventDefault();
      }
      setCurrentPage(1);
      void executeFetch(searchQuery, selectedType, selectedRarity, selectedCost, onlyOwned, 1);
    },
    [executeFetch, searchQuery, selectedType, selectedRarity, selectedCost, onlyOwned]
  );

  // Limpieza completa de filtros y búsqueda
  const handleClear = useCallback(() => {
    setSearchQuery("");
    setCurrentPage(1);
    void executeFetch("", selectedType, selectedRarity, selectedCost, onlyOwned, 1);
  }, [executeFetch, selectedType, selectedRarity, selectedCost, onlyOwned]);

  // Restablecer TODOS los filtros al estado inicial
  const resetFilters = useCallback(() => {
    setSearchQuery("");
    setSelectedTypeState("ALL");
    setSelectedRarityState("ALL");
    setSelectedCostState("ALL");
    setOnlyOwnedState(false);
    setCurrentPage(1);
    void executeFetch("", "ALL", "ALL", "ALL", false, 1);
  }, [executeFetch]);

  // Selección de tipo reactiva: reinicia página a 1
  const setSelectedType = useCallback(
    (type: CardType | "ALL") => {
      setSelectedTypeState(type);
      setCurrentPage(1);
      void executeFetch(searchQuery, type, selectedRarity, selectedCost, onlyOwned, 1);
    },
    [executeFetch, searchQuery, selectedRarity, selectedCost, onlyOwned]
  );

  // Selección de rareza reactiva: reinicia página a 1
  const setSelectedRarity = useCallback(
    (rarity: CardRarity | "ALL") => {
      setSelectedRarityState(rarity);
      setCurrentPage(1);
      void executeFetch(searchQuery, selectedType, rarity, selectedCost, onlyOwned, 1);
    },
    [executeFetch, searchQuery, selectedType, selectedCost, onlyOwned]
  );

  // Selección de costo reactiva: reinicia página a 1
  const setSelectedCost = useCallback(
    (cost: number | "ALL") => {
      setSelectedCostState(cost);
      setCurrentPage(1);
      void executeFetch(searchQuery, selectedType, selectedRarity, cost, onlyOwned, 1);
    },
    [executeFetch, searchQuery, selectedType, selectedRarity, onlyOwned]
  );

  // Toggle de solo propias reactivo: reinicia página a 1
  const setOnlyOwned = useCallback(
    (owned: boolean) => {
      setOnlyOwnedState(owned);
      setCurrentPage(1);
      void executeFetch(searchQuery, selectedType, selectedRarity, selectedCost, owned, 1);
    },
    [executeFetch, searchQuery, selectedType, selectedRarity, selectedCost]
  );

  // Navegación de páginas
  const goToPage = useCallback(
    (targetPage: number) => {
      if (targetPage < 1 || targetPage > totalPages || targetPage === currentPage) {
        return;
      }
      setCurrentPage(targetPage);
      void executeFetch(searchQuery, selectedType, selectedRarity, selectedCost, onlyOwned, targetPage);
    },
    [executeFetch, searchQuery, selectedType, selectedRarity, selectedCost, onlyOwned, totalPages, currentPage]
  );

  const nextPage = useCallback(() => {
    if (currentPage < totalPages) {
      goToPage(currentPage + 1);
    }
  }, [goToPage, currentPage, totalPages]);

  const prevPage = useCallback(() => {
    if (currentPage > 1) {
      goToPage(currentPage - 1);
    }
  }, [goToPage, currentPage]);

  const reload = useCallback(() => {
    void executeFetch(searchQuery, selectedType, selectedRarity, selectedCost, onlyOwned, currentPage);
  }, [executeFetch, searchQuery, selectedType, selectedRarity, selectedCost, onlyOwned, currentPage]);

  // Carga inicial al montar si autoLoad está activo
  useEffect(() => {
    if (autoLoad) {
      void executeFetch(searchQuery, selectedType, selectedRarity, selectedCost, onlyOwned, 1);
    }
    // Solo al montar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    searchQuery,
    setSearchQuery,
    hasSearched,
    isLoading,
    error,
    isCatalogUnavailable,
    results,
    totalResults,
    currentPage,
    totalPages,
    pageSize,
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
    onlyOwned,
    setOnlyOwned,
    resetFilters,
  };
}
