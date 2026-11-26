/** Hook de partida activa: carga Fog of War con ETag/304 y reloj sincronizado contra turn_ends_at. */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { getMatchView } from "../services/matches.api";
import {
  translateArenaError,
  type ActiveMatchViewDTO,
  type ArenaUiError,
} from "../types/partidas.types";

const MATCH_POLL_MS = 5000;

export interface UseActiveMatchResult {
  readonly match: ActiveMatchViewDTO | null;
  readonly isLoading: boolean;
  readonly error: ArenaUiError | null;
  readonly secondsRemaining: number;
  readonly reload: () => Promise<void>;
}

function computeSecondsRemaining(match: ActiveMatchViewDTO | null): number {
  if (!match) return 0;
  const endsMs = Date.parse(match.turn_ends_at);
  if (!Number.isFinite(endsMs)) return match.turn_duration_seconds;
  const raw = Math.ceil((endsMs - Date.now()) / 1000);
  return Math.max(0, Math.min(match.turn_duration_seconds, raw));
}

export function useActiveMatch(matchId: string | null): UseActiveMatchResult {
  const [match, setMatch] = useState<ActiveMatchViewDTO | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(matchId));
  const [error, setError] = useState<ArenaUiError | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState(0);

  const etagRef = useRef<string | null>(null);

  const fetchMatch = useCallback(
    async (signal?: AbortSignal, silent = false) => {
      if (!matchId) return;
      if (!silent) {
        setIsLoading(true);
        setError(null);
      }
      try {
        const res = await getMatchView(matchId, etagRef.current ?? undefined, signal);
        if (signal?.aborted) return;
        if (res.notModified) {
          if (res.etag) etagRef.current = res.etag;
          return;
        }
        etagRef.current = res.etag;
        setMatch(res.data);
        setSecondsRemaining(computeSecondsRemaining(res.data));
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof ApiHttpError && err.code === "solicitud_cancelada") return;
        if (!silent) {
          setError(translateArenaError(err));
        }
      } finally {
        if (!silent && !signal?.aborted) {
          setIsLoading(false);
        }
      }
    },
    [matchId],
  );

  useEffect(() => {
    etagRef.current = null;
    setMatch(null);
    if (!matchId) {
      setIsLoading(false);
      setSecondsRemaining(0);
      return;
    }
    const controller = new AbortController();
    void fetchMatch(controller.signal, false);
    return () => controller.abort();
  }, [matchId, fetchMatch]);

  // Polling condicional ligero (304 Not Modified no sobreescribe el estado)
  const isInProgress = match?.status === "IN_PROGRESS";
  useEffect(() => {
    if (!matchId || !isInProgress) return;
    let activeController: AbortController | null = null;
    const intervalId = window.setInterval(() => {
      activeController?.abort();
      activeController = new AbortController();
      void fetchMatch(activeController.signal, true);
    }, MATCH_POLL_MS);
    return () => {
      activeController?.abort();
      window.clearInterval(intervalId);
    };
  }, [matchId, isInProgress, fetchMatch]);

  // Reloj visual sincronizado con turn_ends_at del servidor
  useEffect(() => {
    if (!match) return;
    setSecondsRemaining(computeSecondsRemaining(match));
    const timerId = window.setInterval(() => {
      setSecondsRemaining(computeSecondsRemaining(match));
    }, 500);
    return () => window.clearInterval(timerId);
  }, [match]);

  const reload = useCallback(async () => {
    etagRef.current = null;
    await fetchMatch(undefined, false);
  }, [fetchMatch]);

  return {
    match,
    isLoading,
    error,
    secondsRemaining,
    reload,
  };
}
