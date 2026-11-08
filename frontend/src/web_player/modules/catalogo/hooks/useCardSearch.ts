import { useState, useCallback, useMemo } from 'react';
import { PokemonCard, CardType, CardRarity } from '../types/card.types';
import { MOCK_CARDS } from '../services/cardsMockData';

export interface SearchFilters {
  query: string;
  type?: CardType | 'ALL';
  rarity?: CardRarity | 'ALL';
}

export interface UseCardSearchResult {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  hasSearched: boolean;
  isLoading: boolean;
  error: string | null;
  results: PokemonCard[];
  totalResults: number;
  handleSearch: (e?: React.FormEvent) => void;
  handleClear: () => void;
  selectedType: CardType | 'ALL';
  setSelectedType: (type: CardType | 'ALL') => void;
  selectedRarity: CardRarity | 'ALL';
  setSelectedRarity: (rarity: CardRarity | 'ALL') => void;
}

const PAGE_SIZE = 15; // 3 filas x 5 columnas

export function useCardSearch(initialQuery = ''): UseCardSearchResult {
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [submittedQuery, setSubmittedQuery] = useState(initialQuery);
  const [hasSearched, setHasSearched] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<CardType | 'ALL'>('ALL');
  const [selectedRarity, setSelectedRarity] = useState<CardRarity | 'ALL'>('ALL');

  // el hook de useCallback actualiza la función handleSearch en el heap cuando 
  // searchQuery cambia, lo que permite que la función tenga acceso al valor más reciente de searchQuery cuando se ejecuta.
  const handleSearch = useCallback((e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }
    setIsLoading(true);
    setError(null);

    // Simular latencia de búsqueda de red/catálogo
    setTimeout(() => {
      setSubmittedQuery(searchQuery);
      setHasSearched(true);
      setIsLoading(false);
    }, 250);
  }, [searchQuery]);

  const handleClear = useCallback(() => {
    setSearchQuery('');
    setSubmittedQuery('');
    setSelectedType('ALL');
    setSelectedRarity('ALL');
    setHasSearched(false);
    setError(null);
  }, []);

  const results = useMemo(() => {
    if (!hasSearched) {
      return [];
    }

    const cleanQuery = submittedQuery.trim().toLowerCase();

    const filtered = MOCK_CARDS.filter((card: PokemonCard) => {
      const matchesText =
        cleanQuery === '' ||
        card.name.toLowerCase().includes(cleanQuery) ||
        card.code.toLowerCase().includes(cleanQuery) ||
        (card.description && card.description.toLowerCase().includes(cleanQuery));

      const matchesType = selectedType === 'ALL' || card.type === selectedType;
      const matchesRarity = selectedRarity === 'ALL' || card.rarity === selectedRarity;

      return matchesText && matchesType && matchesRarity;
    });

    // Retorna como máximo un lote de 15 cartas (3 filas x 5 columnas)
    return filtered.slice(0, PAGE_SIZE);
  }, [hasSearched, submittedQuery, selectedType, selectedRarity]);

  return {
    searchQuery,
    setSearchQuery,
    hasSearched,
    isLoading,
    error,
    results,
    totalResults: results.length,
    handleSearch,
    handleClear,
    selectedType,
    setSelectedType,
    selectedRarity,
    setSelectedRarity,
  };
}
