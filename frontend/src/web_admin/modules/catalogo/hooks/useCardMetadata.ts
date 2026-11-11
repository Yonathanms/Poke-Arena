import { useEffect, useState } from "react";
import { fetchCardTypes, fetchCardRarities } from "../services/catalog.api";
import type { CardTypeOptionDTO, CardRarityOptionDTO } from "../types/card-admin.types";

export interface UseCardMetadataResult {
  readonly types: readonly CardTypeOptionDTO[];
  readonly rarities: readonly CardRarityOptionDTO[];
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly reload: () => Promise<void>;
}

export function useCardMetadata(options?: { fetchImpl?: typeof fetch }): UseCardMetadataResult {
  const [types, setTypes] = useState<readonly CardTypeOptionDTO[]>([]);
  const [rarities, setRarities] = useState<readonly CardRarityOptionDTO[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetadata = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [fetchedTypes, fetchedRarities] = await Promise.all([
        fetchCardTypes({ fetchImpl: options?.fetchImpl }),
        fetchCardRarities({ fetchImpl: options?.fetchImpl }),
      ]);
      setTypes(fetchedTypes);
      setRarities(fetchedRarities);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar tipos y rarezas.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadMetadata();
  }, [options?.fetchImpl]);

  return {
    types,
    rarities,
    isLoading,
    error,
    reload: loadMetadata,
  };
}

