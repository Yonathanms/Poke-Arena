/** Hook de emparejamiento: reanudación al montar, polling ETag/304 cada 2.5s y oferta Bot. */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import { getActiveMatch } from "../services/matches.api";
import {
  acceptBotMatch,
  cancelMatchmaking,
  getCurrentMatchmaking,
  getMatchmakingById,
  startMatchmaking,
} from "../services/matchmaking.api";
import {
  translateArenaError,
  type ArenaUiError,
  type MatchContext,
  type MatchSearchDTO,
} from "../types/partidas.types";

const POLL_INTERVAL_MS = 2500;

export interface UseMatchmakingOptions {
  readonly enabled?: boolean;
  readonly onMatchFound?: (matchId: string) => void;
  readonly onActiveSearchResumed?: () => void;
}

export interface UseMatchmakingResult {
  readonly search: MatchSearchDTO | null;
  readonly activeMatchId: string | null;
  readonly liveElapsedSeconds: number;
  readonly isInitializing: boolean;
  readonly isSubmitting: boolean;
  readonly isCancelling: boolean;
  readonly isAcceptingBot: boolean;
  readonly error: ArenaUiError | null;
  readonly notice: string | null;
  readonly startSearch: (deckId: string, context: MatchContext) => Promise<void>;
  readonly cancelSearch: () => Promise<void>;
  readonly acceptBot: () => Promise<void>;
  readonly refreshStatus: (options?: { readonly autoEnterMatch?: boolean }) => Promise<void>;
  readonly dismissError: () => void;
  readonly dismissNotice: () => void;
}

export function useMatchmaking(options: UseMatchmakingOptions = {}): UseMatchmakingResult {
  const { enabled = true, onMatchFound, onActiveSearchResumed } = options;

  const [search, setSearch] = useState<MatchSearchDTO | null>(null);
  const [activeMatchId, setActiveMatchId] = useState<string | null>(null);
  const [liveElapsedSeconds, setLiveElapsedSeconds] = useState(0);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isAcceptingBot, setIsAcceptingBot] = useState(false);
  const [error, setError] = useState<ArenaUiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const etagRef = useRef<string | null>(null);
  const clockAnchorRef = useRef<{ baseSeconds: number; anchoredAtMs: number }>({
    baseSeconds: 0,
    anchoredAtMs: Date.now(),
  });
  const onMatchFoundRef = useRef(onMatchFound);
  const onResumedRef = useRef(onActiveSearchResumed);
  onMatchFoundRef.current = onMatchFound;
  onResumedRef.current = onActiveSearchResumed;

  const syncAnchor = useCallback((dto: MatchSearchDTO | null) => {
    if (!dto) {
      setLiveElapsedSeconds(0);
      return;
    }
    const base = Math.max(0, Math.floor(dto.elapsed_seconds));
    clockAnchorRef.current = { baseSeconds: base, anchoredAtMs: Date.now() };
    setLiveElapsedSeconds(base);
  }, []);

  const handleResolvedMatch = useCallback((matchId: string) => {
    etagRef.current = null;
    setSearch(null);
    setActiveMatchId(matchId);
    onMatchFoundRef.current?.(matchId);
  }, []);

  const refreshStatus = useCallback(async (opts?: { readonly autoEnterMatch?: boolean }) => {
    if (!enabled) return;
    const autoEnterMatch = opts?.autoEnterMatch ?? true;
    setIsInitializing(true);
    try {
      const [activeMatch, currentSearchRes] = await Promise.all([
        getActiveMatch(),
        getCurrentMatchmaking(),
      ]);

      if (activeMatch) {
        if (autoEnterMatch) {
          handleResolvedMatch(activeMatch.match_id);
        } else {
          etagRef.current = null;
          setSearch(null);
          setActiveMatchId(activeMatch.match_id);
        }
        return;
      }
      setActiveMatchId(null);

      if (currentSearchRes.status === 204 || !currentSearchRes.data) {
        etagRef.current = null;
        setSearch(null);
        return;
      }

      const dto = currentSearchRes.data;
      if (dto.status === "MATCHED" && dto.match_id) {
        if (autoEnterMatch) {
          handleResolvedMatch(dto.match_id);
        } else {
          etagRef.current = null;
          setSearch(null);
          setActiveMatchId(dto.match_id);
        }
        return;
      }

      if (dto.status === "SEARCHING") {
        etagRef.current = currentSearchRes.etag;
        setSearch(dto);
        syncAnchor(dto);
        onResumedRef.current?.();
      } else {
        etagRef.current = null;
        setSearch(null);
      }
    } catch (err) {
      if (err instanceof ApiHttpError && err.code === "solicitud_cancelada") return;
      setError(translateArenaError(err));
    } finally {
      setIsInitializing(false);
    }
  }, [enabled, handleResolvedMatch, syncAnchor]);

  useEffect(() => {
    if (!enabled) {
      setIsInitializing(false);
      return;
    }
    void refreshStatus();
  }, [enabled, refreshStatus]);

  // Polling ligero sobre GET /player/matchmaking/{search_id} con If-None-Match (304)
  const searchId = search?.status === "SEARCHING" ? search.search_id : null;
  useEffect(() => {
    if (!enabled || !searchId) return;

    let cancelled = false;
    let activeController: AbortController | null = null;

    const poll = async () => {
      activeController?.abort();
      activeController = new AbortController();
      try {
        const res = await getMatchmakingById(
          searchId,
          etagRef.current ?? undefined,
          activeController.signal,
        );
        if (cancelled) return;
        if (res.notModified) {
          if (res.etag) etagRef.current = res.etag;
          return;
        }
        const dto = res.data;
        etagRef.current = res.etag;

        if (dto.status === "MATCHED" && dto.match_id) {
          handleResolvedMatch(dto.match_id);
          return;
        }
        if (dto.status === "EXPIRED") {
          etagRef.current = null;
          setSearch(null);
          setNotice("La búsqueda expiró por inactividad.");
          return;
        }
        if (dto.status === "CANCELLED") {
          etagRef.current = null;
          setSearch(null);
          return;
        }
        setSearch(dto);
        syncAnchor(dto);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiHttpError && err.code === "solicitud_cancelada") return;
        if (err instanceof ApiHttpError && err.status === 404) {
          etagRef.current = null;
          setSearch(null);
          return;
        }
        setError(translateArenaError(err));
      }
    };

    const intervalId = window.setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      activeController?.abort();
      window.clearInterval(intervalId);
    };
  }, [enabled, searchId, handleResolvedMatch, syncAnchor]);

  // Cronómetro visual de 1 s en espera (solo visual; el servidor autoriza la oferta Bot)
  useEffect(() => {
    if (!searchId) return;
    const tickId = window.setInterval(() => {
      const { baseSeconds, anchoredAtMs } = clockAnchorRef.current;
      const delta = Math.max(0, Math.floor((Date.now() - anchoredAtMs) / 1000));
      setLiveElapsedSeconds(baseSeconds + delta);
    }, 1000);
    return () => window.clearInterval(tickId);
  }, [searchId]);

  const startSearch = useCallback(
    async (deckId: string, context: MatchContext) => {
      setIsSubmitting(true);
      setError(null);
      setNotice(null);
      try {
        const res = await startMatchmaking(deckId, context);
        const dto = res.data;
        if (dto.status === "MATCHED" && dto.match_id) {
          handleResolvedMatch(dto.match_id);
          return;
        }
        etagRef.current = res.etag;
        setSearch(dto);
        syncAnchor(dto);
        if (res.status !== 201) {
          setNotice("Ya tenías una búsqueda abierta; la reanudamos automáticamente.");
        }
      } catch (err) {
        if (err instanceof ApiHttpError && err.code === "partida_activa") {
          const active = await getActiveMatch().catch(() => null);
          if (active) {
            setActiveMatchId(active.match_id);
          }
        }
        setError(translateArenaError(err));
      } finally {
        setIsSubmitting(false);
      }
    },
    [handleResolvedMatch, syncAnchor],
  );

  const cancelSearch = useCallback(async () => {
    if (!search) return;
    setIsCancelling(true);
    setError(null);
    setNotice(null);
    try {
      await cancelMatchmaking(search.search_id);
      etagRef.current = null;
      setSearch(null);
      setNotice("Búsqueda cancelada. Ya puedes elegir otro mazo.");
    } catch (err) {
      if (err instanceof ApiHttpError && err.code === "busqueda_ya_emparejada") {
        const active = await getActiveMatch().catch(() => null);
        if (active) {
          handleResolvedMatch(active.match_id);
          return;
        }
      }
      if (
        err instanceof ApiHttpError &&
        (err.code === "busqueda_expired" || err.code === "busqueda_cancelled")
      ) {
        etagRef.current = null;
        setSearch(null);
        setNotice("La búsqueda ya había finalizado.");
        return;
      }
      setError(translateArenaError(err));
    } finally {
      setIsCancelling(false);
    }
  }, [search, handleResolvedMatch]);

  const acceptBot = useCallback(async () => {
    if (!search) return;
    setIsAcceptingBot(true);
    setError(null);
    setNotice(null);
    try {
      const res = await acceptBotMatch(search.search_id);
      const dto = res.data;
      if (dto.status === "MATCHED" && dto.match_id) {
        handleResolvedMatch(dto.match_id);
        return;
      }
      etagRef.current = res.etag;
      setSearch(dto);
      syncAnchor(dto);
    } catch (err) {
      if (err instanceof ApiHttpError && err.code === "busqueda_ya_emparejada") {
        const active = await getActiveMatch().catch(() => null);
        if (active) {
          handleResolvedMatch(active.match_id);
          return;
        }
      }
      setError(translateArenaError(err));
    } finally {
      setIsAcceptingBot(false);
    }
  }, [search, handleResolvedMatch, syncAnchor]);

  return {
    search,
    activeMatchId,
    liveElapsedSeconds,
    isInitializing,
    isSubmitting,
    isCancelling,
    isAcceptingBot,
    error,
    notice,
    startSearch,
    cancelSearch,
    acceptBot,
    refreshStatus,
    dismissError: () => setError(null),
    dismissNotice: () => setNotice(null),
  };
}
