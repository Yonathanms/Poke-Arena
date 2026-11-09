/**
 * Hook para cargar y gestionar el estado del perfil del jugador desde PostgreSQL.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchAuthenticatedProfile } from "../services/vista_principal.api";
import { ApiHttpError } from "../../../../shared/services/http-client";
import type { PlayerProfileDTO, PlayerProfileState } from "../types/vista_principal.types";

export function usePlayerProfile(): PlayerProfileState {
  const [profile, setProfile] = useState<PlayerProfileDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAuthenticatedProfile();
      setProfile(data);
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setError(err.detail || "Error al cargar el perfil de jugador desde la base de datos.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Error desconocido al obtener perfil.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  return {
    profile,
    isLoading,
    error,
    reload: loadProfile,
  };
}

