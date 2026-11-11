/**
 * Hook React para consultar las habilidades existentes en el catálogo (`GET /api/v1/content/abilities`).
 * Incluye desde el inicio la habilidad por defecto "Sin Habilidad" (`HAB-000`).
 */

import { useCallback, useEffect, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { fetchSelectableAbilities } from "../services/catalog.api";
import type { AbilityOptionDTO } from "../types/card-admin.types";

const DEFAULT_ABILITIES: readonly AbilityOptionDTO[] = [
  { code: "HAB-000", name: "Sin Habilidad" },
];

export interface UseAbilitiesResult {
  readonly abilities: readonly AbilityOptionDTO[];
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly reload: () => Promise<void>;
}

export function useAbilities(): UseAbilitiesResult {
  const [abilities, setAbilities] = useState<readonly AbilityOptionDTO[]>(DEFAULT_ABILITIES);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const items = await fetchSelectableAbilities();
      setAbilities(items.length > 0 ? items : DEFAULT_ABILITIES);
    } catch (err: unknown) {
      const message =
        err instanceof ApiHttpError
          ? err.detail
          : "No se pudo consultar el catálogo de habilidades.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { abilities, isLoading, error, reload };
}
