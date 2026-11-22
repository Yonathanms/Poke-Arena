/**
 * Hook React liviano para el onboarding de colección inicial (US 3.1.1).
 *
 * Toda regla de negocio y máquina de estados autoritativa vive en el backend
 * (`GET /api/v1/player/initial-pack` y `POST /api/v1/player/initial-pack/open`).
 * Este hook únicamente sincroniza la vista con el estado devuelto por la API.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import {
  getActiveSessionSnapshot,
  subscribeToSessionChanges,
} from "../../../../web_admin/modules/auth/services/session-store";
import {
  fetchInitialPackStatusWithMeta,
  openInitialPackWithMeta,
  type InitialPackRequestOptions,
} from "../services/initial_pack.api";
import {
  INITIAL_COLLECTION_CONSTANTS,
  type InitialPackCardDTO,
  type InitialPackErrorInfo,
  type InitialPackFailedOperation,
  type InitialPackPresentationPhase,
  type InitialPackState,
  type InitialPackStatusDTO,
} from "../types/initial_pack.types";

export interface InitialPackOnboardingState {
  readonly phase: InitialPackPresentationPhase;
  readonly backendState: InitialPackState | null;
  readonly received: boolean;
  readonly opened: boolean;
  readonly openedAt: string | null;
  readonly retainedCards: readonly InitialPackCardDTO[];
  readonly grantedCubes: number;
  readonly error: InitialPackErrorInfo | null;
  readonly lastCorrelationId: string | null;
  readonly activeUserId: string | null;
}

export interface UseInitialPackOnboardingResult extends InitialPackOnboardingState {
  readonly isLoading: boolean;
  readonly isOpening: boolean;
  readonly isPendingCatalog: boolean;
  readonly isReadyToOpen: boolean;
  readonly isRevealed: boolean;
  readonly isCompleted: boolean;
  readonly canOpenPack: boolean;
  readonly openPack: (options?: InitialPackRequestOptions) => Promise<InitialPackStatusDTO | null>;
  readonly refreshStatus: (
    options?: InitialPackRequestOptions
  ) => Promise<InitialPackStatusDTO | null>;
  readonly completeReveal: () => void;
  readonly clearError: () => void;
}

const EMPTY_CARDS: readonly InitialPackCardDTO[] = [];

const INITIAL_STATE: InitialPackOnboardingState = {
  phase: "IDLE",
  backendState: null,
  received: false,
  opened: false,
  openedAt: null,
  retainedCards: EMPTY_CARDS,
  grantedCubes: 0,
  error: null,
  lastCorrelationId: null,
  activeUserId: null,
};

export function mapInitialPackError(
  error: unknown,
  operation: InitialPackFailedOperation
): InitialPackErrorInfo {
  if (error instanceof ApiHttpError) {
    const isNetwork = error.isNetworkError || error.status === 0;
    const isExpired = error.status === 401;
    const title = isExpired
      ? "Sesión expirada o no válida"
      : isNetwork
        ? "Sin conexión con el servidor"
        : error.title || "No se pudo procesar el paquete inicial";
    const userGuidance = isExpired
      ? "Inicia sesión nuevamente con tu cuenta de Google para continuar."
      : isNetwork
        ? "Verifica tu conexión de red e inténtalo nuevamente."
        : "Inténtalo de nuevo o vuelve a iniciar sesión si el problema persiste.";

    return {
      status: error.status,
      code: error.code,
      title,
      detail: error.detail,
      userGuidance,
      correlationId: error.correlationId,
      operation,
      isNetworkError: isNetwork,
      isSessionExpired: isExpired,
      isRetryable: isNetwork || error.status >= 500 || error.code === "paquete_sin_abrir",
    };
  }

  return {
    status: 500,
    code: "error_inesperado",
    title: "Error inesperado",
    detail:
      error instanceof Error
        ? error.message
        : "Ocurrió un fallo inesperado al gestionar el paquete inicial.",
    userGuidance: "Inténtalo nuevamente.",
    correlationId: null,
    operation,
    isNetworkError: false,
    isSessionExpired: false,
    isRetryable: true,
  };
}

export function useInitialPackOnboarding(options?: {
  readonly fetchImpl?: typeof fetch;
}): UseInitialPackOnboardingResult {
  const fetchImpl = options?.fetchImpl;
  const [state, setState] = useState<InitialPackOnboardingState>(INITIAL_STATE);
  const openingRef = useRef(false);
  const stateRef = useRef(state);
  stateRef.current = state;

  const refreshStatus = useCallback(
    async (reqOptions?: InitialPackRequestOptions): Promise<InitialPackStatusDTO | null> => {
      const session = getActiveSessionSnapshot();
      if (!session || session.role !== "PLAYER") {
        setState(INITIAL_STATE);
        return null;
      }

      setState((prev) => ({
        ...prev,
        phase: "LOADING",
        error: null,
        activeUserId: session.userId,
      }));

      try {
        const res = await fetchInitialPackStatusWithMeta({
          ...reqOptions,
          fetchImpl: reqOptions?.fetchImpl ?? fetchImpl,
        });
        const dto = res.data;
        setState({
          phase: dto.state,
          backendState: dto.state,
          received: dto.received,
          opened: dto.opened,
          openedAt: dto.opened_at,
          retainedCards: dto.state === "READY_TO_OPEN" ? dto.cards : EMPTY_CARDS,
          grantedCubes:
            dto.state === "PENDING_CATALOG" ? 0 : INITIAL_COLLECTION_CONSTANTS.GRANTED_CUBES,
          error: null,
          lastCorrelationId: res.correlationId,
          activeUserId: session.userId,
        });
        return dto;
      } catch (err) {
        const mapped = mapInitialPackError(err, "FETCH_STATUS");
        setState((prev) => ({
          ...prev,
          phase: "ERROR",
          error: mapped,
          lastCorrelationId: mapped.correlationId ?? prev.lastCorrelationId,
          activeUserId: session.userId,
        }));
        return null;
      }
    },
    [fetchImpl]
  );

  useEffect(() => {
    const cargarSiJugador = () => {
      const session = getActiveSessionSnapshot();
      if (!session || session.role !== "PLAYER") {
        setState(INITIAL_STATE);
        return;
      }
      void refreshStatus();
    };

    cargarSiJugador();
    return subscribeToSessionChanges((event) => {
      if (!event.session || event.session.role !== "PLAYER") {
        setState(INITIAL_STATE);
      } else if (event.session.userId !== stateRef.current.activeUserId) {
        void refreshStatus();
      }
    });
  }, [refreshStatus]);

  const openPack = useCallback(
    async (reqOptions?: InitialPackRequestOptions): Promise<InitialPackStatusDTO | null> => {
      const current = stateRef.current;
      if (openingRef.current || current.backendState !== "READY_TO_OPEN") {
        return null;
      }

      openingRef.current = true;
      const cardsToReveal = current.retainedCards;
      setState((prev) => ({ ...prev, phase: "OPENING", error: null }));

      try {
        const res = await openInitialPackWithMeta({
          ...reqOptions,
          fetchImpl: reqOptions?.fetchImpl ?? fetchImpl,
        });
        const dto = res.data;
        const revealedCards = dto.cards.length > 0 ? dto.cards : cardsToReveal;
        setState((prev) => ({
          ...prev,
          phase: revealedCards.length > 0 ? "REVEALED" : "COMPLETED",
          backendState: dto.state,
          received: dto.received,
          opened: dto.opened,
          openedAt: dto.opened_at,
          retainedCards: revealedCards,
          grantedCubes: INITIAL_COLLECTION_CONSTANTS.GRANTED_CUBES,
          error: null,
          lastCorrelationId: res.correlationId,
        }));
        return dto;
      } catch (err) {
        const mapped = mapInitialPackError(err, "OPEN_PACK");
        setState((prev) => ({
          ...prev,
          phase: "ERROR",
          error: mapped,
          lastCorrelationId: mapped.correlationId ?? prev.lastCorrelationId,
        }));
        return null;
      } finally {
        openingRef.current = false;
      }
    },
    [fetchImpl]
  );

  const completeReveal = useCallback(() => {
    setState((prev) =>
      prev.phase === "REVEALED" ? { ...prev, phase: "COMPLETED", error: null } : prev
    );
  }, []);

  const clearError = useCallback(() => {
    setState((prev) =>
      prev.error ? { ...prev, phase: prev.backendState ?? "IDLE", error: null } : prev
    );
  }, []);

  return {
    ...state,
    isLoading: state.phase === "LOADING",
    isOpening: state.phase === "OPENING",
    isPendingCatalog: state.phase === "PENDING_CATALOG",
    isReadyToOpen: state.phase === "READY_TO_OPEN",
    isRevealed: state.phase === "REVEALED",
    isCompleted: state.phase === "COMPLETED",
    canOpenPack:
      state.backendState === "READY_TO_OPEN" &&
      (state.phase === "READY_TO_OPEN" || state.phase === "ERROR"),
    openPack,
    refreshStatus,
    completeReveal,
    clearError,
  };
}
