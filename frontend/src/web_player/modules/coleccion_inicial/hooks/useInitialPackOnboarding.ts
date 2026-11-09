/**
 * Hook React y controlador determinista de estados para el onboarding de jugador
 * (US 3.1.1 — Recibir Colección Inicial).
 *
 * Responsabilidades:
 * 1. Consultar automáticamente `GET /api/v1/player/initial-pack` cuando existe una
 *    sesión activa con rol `PLAYER`, evitando llamadas duplicadas o innecesarias.
 * 2. Distinguir estrictamente entre el estado persistido del backend (`backendState`:
 *    `"PENDING_CATALOG" | "READY_TO_OPEN" | "COMPLETED"`) y la fase de presentación
 *    del cliente (`phase`: `"IDLE" | "LOADING" | "PENDING_CATALOG" | "READY_TO_OPEN" |
 *    "OPENING" | "REVEALED" | "COMPLETED" | "ERROR"`).
 * 3. Conservar en memoria las 15 cartas (`retainedCards`) recibidas en `READY_TO_OPEN`
 *    para que, cuando `POST /api/v1/player/initial-pack/open` responda `COMPLETED` con
 *    `cards: []`, la interfaz pueda presentar la revelación visual (`REVEALED`) antes
 *    de avanzar al panel principal (`COMPLETED`).
 * 4. Proteger `openPack()` contra doble clic o ejecuciones concurrentes mediante bloqueo
 *    síncrono en memoria.
 * 5. Reconciliar automáticamente el estado con `GET /api/v1/player/initial-pack` si la
 *    respuesta de `POST /api/v1/player/initial-pack/open` se pierde por fallo de red o
 *    resultado incierto (`500`, `502`, `503`), evitando declarar fallida una apertura
 *    que ya quedó confirmada en PostgreSQL.
 * 6. Reconocer directamente `COMPLETED` al recargar la página o iniciar sesión con un
 *    paquete previamente abierto, sin reiniciar el proceso ni repetir llamadas HTTP.
 * 7. Reaccionar a la expiración (`401` / `expired`) o cierre de sesión (`manual_logout`)
 *    sincronizándose con `session-store.ts`.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import {
  getActiveSessionSnapshot,
  subscribeToSessionChanges,
} from "../../../../web_admin/modules/auth/services/session-store";
import type {
  ActiveSessionSnapshot,
  SessionChangeEvent,
} from "../../../../web_admin/modules/auth/types/auth.types";
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

/** Estado inmutable expuesto por el controlador y por `useInitialPackOnboarding`. */
export interface InitialPackOnboardingState {
  readonly phase: InitialPackPresentationPhase;
  readonly backendState: InitialPackState | null;
  readonly received: boolean;
  readonly opened: boolean;
  readonly openedAt: string | null;
  /**
   * Cartas comunes asignadas al jugador.
   * Se puebla en `READY_TO_OPEN` (15 cartas) y se conserva en memoria durante
   * `OPENING`, `REVEALED` y posibles errores de apertura para permitir reintentos
   * y visualización sin perder la lista cuando `POST /open` devuelve `cards: []`.
   */
  readonly retainedCards: readonly InitialPackCardDTO[];
  readonly grantedCubes: number;
  readonly error: InitialPackErrorInfo | null;
  readonly lastCorrelationId: string | null;
  readonly activeUserId: string | null;
}

/** Opciones de inyección para pruebas unitarias deterministas sin red ni timers reales. */
export interface InitialPackOnboardingControllerOptions {
  readonly fetchImpl?: typeof fetch;
  readonly getSession?: () => ActiveSessionSnapshot | null;
  readonly subscribeSession?: (listener: (event: SessionChangeEvent) => void) => () => void;
}

export type InitialPackOnboardingListener = (state: InitialPackOnboardingState) => void;

const EMPTY_CARDS: readonly InitialPackCardDTO[] = Object.freeze([]);

function createInitialOnboardingState(activeUserId: string | null = null): InitialPackOnboardingState {
  return Object.freeze({
    phase: "IDLE",
    backendState: null,
    received: false,
    opened: false,
    openedAt: null,
    retainedCards: EMPTY_CARDS,
    grantedCubes: 0,
    error: null,
    lastCorrelationId: null,
    activeUserId,
  });
}

/**
 * Determina si un fallo durante `POST /api/v1/player/initial-pack/open` dejó un
 * resultado incierto en el servidor y amerita una consulta de reconciliación
 * (`GET /api/v1/player/initial-pack`) antes de declarar fallida la apertura.
 */
function shouldReconcileAfterOpenFailure(error: unknown): boolean {
  if (error instanceof ApiHttpError) {
    if (error.isNetworkError || error.status === 0) {
      return true;
    }
    if (error.status === 500 || error.status === 502 || error.status === 503 || error.status === 504) {
      return true;
    }
    return false;
  }
  return true;
}

/**
 * Traduce cualquier error HTTP o de red en `InitialPackErrorInfo` con semántica
 * clara para los códigos RFC 7807 de `/api/v1/player/initial-pack`.
 */
export function mapInitialPackError(
  error: unknown,
  operation: InitialPackFailedOperation
): InitialPackErrorInfo {
  if (error instanceof ApiHttpError) {
    if (error.status === 401) {
      return Object.freeze({
        status: 401,
        code: error.code,
        title: "Sesión expirada o no válida",
        detail: error.detail,
        userGuidance: "Inicia sesión nuevamente con tu cuenta de Google para continuar.",
        correlationId: error.correlationId,
        operation,
        isNetworkError: false,
        isSessionExpired: true,
        isRetryable: false,
      });
    }

    if (error.status === 403) {
      if (error.code === "paquete_sin_abrir") {
        return Object.freeze({
          status: 403,
          code: error.code,
          title: "Paquete inicial pendiente de apertura",
          detail: error.detail,
          userGuidance: "Debes abrir tu paquete inicial antes de acceder a esta sección.",
          correlationId: error.correlationId,
          operation,
          isNetworkError: false,
          isSessionExpired: false,
          isRetryable: true,
        });
      }

      return Object.freeze({
        status: 403,
        code: error.code,
        title: "Cuenta no elegible para colección de jugador",
        detail: error.detail,
        userGuidance:
          "Esta operación está reservada exclusivamente para cuentas con rol de jugador (PLAYER).",
        correlationId: error.correlationId,
        operation,
        isNetworkError: false,
        isSessionExpired: false,
        isRetryable: false,
      });
    }

    if (error.status === 409) {
      if (error.code === "paquete_pendiente") {
        return Object.freeze({
          status: 409,
          code: error.code,
          title: "Colección inicial aún no disponible",
          detail: error.detail,
          userGuidance:
            "El catálogo aún no cuenta con las 15 cartas comunes requeridas. Cierra sesión e intenta ingresar más tarde.",
          correlationId: error.correlationId,
          operation,
          isNetworkError: false,
          isSessionExpired: false,
          isRetryable: false,
        });
      }

      return Object.freeze({
        status: 409,
        code: error.code,
        title: "Inconsistencia en el paquete inicial",
        detail: error.detail,
        userGuidance:
          "Se detectó un estado inconsistente en tu perfil o inventario inicial. Contacta al administrador.",
        correlationId: error.correlationId,
        operation,
        isNetworkError: false,
        isSessionExpired: false,
        isRetryable: false,
      });
    }

    if (error.status === 422) {
      return Object.freeze({
        status: 422,
        code: error.code,
        title: "Solicitud de paquete inicial inválida",
        detail: error.detail,
        userGuidance: "La solicitud enviada no cumple el formato esperado por el servidor.",
        correlationId: error.correlationId,
        operation,
        isNetworkError: false,
        isSessionExpired: false,
        isRetryable: false,
      });
    }

    if (error.status === 503) {
      return Object.freeze({
        status: 503,
        code: error.code,
        title: "Servicio de colección temporalmente no disponible",
        detail: error.detail,
        userGuidance:
          "El servidor no pudo consultar o confirmar tu paquete inicial en este momento. Inténtalo de nuevo en unos segundos.",
        correlationId: error.correlationId,
        operation,
        isNetworkError: false,
        isSessionExpired: false,
        isRetryable: true,
      });
    }

    if (error.isNetworkError || error.status === 0) {
      return Object.freeze({
        status: 0,
        code: error.code,
        title: "Sin conexión con el servidor",
        detail: error.detail,
        userGuidance: "Verifica tu conexión de red e inténtalo nuevamente.",
        correlationId: null,
        operation,
        isNetworkError: true,
        isSessionExpired: false,
        isRetryable: true,
      });
    }

    return Object.freeze({
      status: error.status,
      code: error.code,
      title: "No se pudo procesar el paquete inicial",
      detail: error.detail,
      userGuidance: "Intenta nuevamente o vuelve a iniciar sesión si el problema persiste.",
      correlationId: error.correlationId,
      operation,
      isNetworkError: false,
      isSessionExpired: false,
      isRetryable: error.status >= 500,
    });
  }

  return Object.freeze({
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
  });
}

/**
 * Controlador determinista del flujo de onboarding de paquete inicial.
 * Desacopla la máquina de estados del árbol de renderizado de React para facilitar
 * pruebas unitarias exhaustivas de concurrencia, reconciliación y expiración.
 */
export class InitialPackOnboardingController {
  private state: InitialPackOnboardingState = createInitialOnboardingState();
  private readonly listeners = new Set<InitialPackOnboardingListener>();
  private readonly fetchImpl?: typeof fetch;
  private readonly getSession: () => ActiveSessionSnapshot | null;
  private readonly subscribeSession: (listener: (event: SessionChangeEvent) => void) => () => void;

  private unsubscribeSession: (() => void) | null = null;
  private started = false;
  private generation = 0;
  private loadedForUserId: string | null = null;
  private inFlightFetchPromise: Promise<InitialPackStatusDTO | null> | null = null;
  private inFlightOpenPromise: Promise<InitialPackStatusDTO | null> | null = null;

  public constructor(options?: InitialPackOnboardingControllerOptions) {
    this.fetchImpl = options?.fetchImpl;
    this.getSession = options?.getSession ?? getActiveSessionSnapshot;
    this.subscribeSession = options?.subscribeSession ?? subscribeToSessionChanges;
  }

  public getState(): InitialPackOnboardingState {
    return this.state;
  }

  public subscribe(listener: InitialPackOnboardingListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private setState(
    updater:
      | InitialPackOnboardingState
      | ((prev: InitialPackOnboardingState) => InitialPackOnboardingState)
  ): void {
    const next = typeof updater === "function" ? updater(this.state) : updater;
    this.state = Object.freeze({ ...next });
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }

  /**
   * Inicia la suscripción al almacén de sesión y, si hay un jugador autenticado,
   * dispara la consulta inicial (`GET /api/v1/player/initial-pack`) exactamente una vez.
   */
  public start(): void {
    if (!this.started) {
      this.started = true;
      this.unsubscribeSession = this.subscribeSession((event) => {
        this.handleSessionChange(event);
      });
    }

    const currentSession = this.getSession();
    this.syncWithSessionSnapshot(currentSession);
  }

  public dispose(): void {
    if (this.unsubscribeSession !== null) {
      this.unsubscribeSession();
      this.unsubscribeSession = null;
    }
    this.started = false;
    this.generation += 1;
    this.inFlightFetchPromise = null;
    this.inFlightOpenPromise = null;
  }

  private handleSessionChange(event: SessionChangeEvent): void {
    if (event.session === null) {
      this.generation += 1;
      this.inFlightFetchPromise = null;
      this.inFlightOpenPromise = null;
      this.loadedForUserId = null;

      if (event.reason === "expired" || event.reason === "unauthorized_401") {
        this.setState((prev) => ({
          ...prev,
          phase: "ERROR",
          error: Object.freeze({
            status: 401,
            code: event.reason === "expired" ? "sesion_expirada" : "no_autenticado",
            title: "Sesión expirada",
            detail: "Tu sesión de Poké-Arena ha expirado.",
            userGuidance: "Inicia sesión nuevamente con tu cuenta de Google para continuar.",
            correlationId: prev.lastCorrelationId,
            operation: prev.phase === "OPENING" ? "OPEN_PACK" : "FETCH_STATUS",
            isNetworkError: false,
            isSessionExpired: true,
            isRetryable: false,
          }),
        }));
        return;
      }

      // Cierre manual de sesión: limpiar todo estado en memoria
      this.setState(createInitialOnboardingState(null));
      return;
    }

    this.syncWithSessionSnapshot(event.session);
  }

  private syncWithSessionSnapshot(session: ActiveSessionSnapshot | null): void {
    if (session === null || session.role !== "PLAYER") {
      if (this.state.activeUserId !== null || this.state.phase !== "IDLE") {
        this.generation += 1;
        this.inFlightFetchPromise = null;
        this.inFlightOpenPromise = null;
        this.loadedForUserId = null;
        this.setState(createInitialOnboardingState(null));
      }
      return;
    }

    // Si cambió de jugador, reiniciar estado antes de consultar el nuevo usuario
    if (this.state.activeUserId !== null && this.state.activeUserId !== session.userId) {
      this.generation += 1;
      this.inFlightFetchPromise = null;
      this.inFlightOpenPromise = null;
      this.loadedForUserId = null;
      this.setState(createInitialOnboardingState(session.userId));
    }

    // Evitar solicitudes HTTP innecesarias si ya se cargó o está en vuelo para este jugador
    if (
      this.loadedForUserId === session.userId ||
      this.inFlightFetchPromise !== null ||
      this.inFlightOpenPromise !== null
    ) {
      return;
    }

    void this.fetchStatusForActivePlayer();
  }

  private applyStatusFromGet(
    dto: InitialPackStatusDTO,
    correlationId: string | null,
    userId: string
  ): void {
    this.loadedForUserId = userId;

    if (dto.state === "PENDING_CATALOG") {
      this.setState({
        phase: "PENDING_CATALOG",
        backendState: "PENDING_CATALOG",
        received: false,
        opened: false,
        openedAt: null,
        retainedCards: EMPTY_CARDS,
        grantedCubes: 0,
        error: null,
        lastCorrelationId: correlationId,
        activeUserId: userId,
      });
      return;
    }

    if (dto.state === "READY_TO_OPEN") {
      this.setState({
        phase: "READY_TO_OPEN",
        backendState: "READY_TO_OPEN",
        received: true,
        opened: false,
        openedAt: null,
        retainedCards: dto.cards,
        grantedCubes: INITIAL_COLLECTION_CONSTANTS.GRANTED_CUBES,
        error: null,
        lastCorrelationId: correlationId,
        activeUserId: userId,
      });
      return;
    }

    // dto.state === "COMPLETED"
    // Si ya veníamos mostrando la revelación en esta sesión con las 15 cartas en memoria,
    // conservar las cartas retenidas; si es una carga inicial o recarga con paquete ya
    // completado, pasar directamente a COMPLETED sin reiniciar el proceso.
    const shouldStayRevealed =
      this.state.activeUserId === userId &&
      this.state.phase === "REVEALED" &&
      this.state.retainedCards.length === INITIAL_COLLECTION_CONSTANTS.REQUIRED_COMMON_CARDS;

    this.setState({
      phase: shouldStayRevealed ? "REVEALED" : "COMPLETED",
      backendState: "COMPLETED",
      received: true,
      opened: true,
      openedAt: dto.opened_at,
      retainedCards: shouldStayRevealed ? this.state.retainedCards : EMPTY_CARDS,
      grantedCubes: INITIAL_COLLECTION_CONSTANTS.GRANTED_CUBES,
      error: null,
      lastCorrelationId: correlationId,
      activeUserId: userId,
    });
  }

  /**
   * Consulta explícitamente `GET /api/v1/player/initial-pack` para el jugador activo.
   * Si ya hay una consulta en curso, reutiliza la promesa existente sin duplicar la llamada.
   */
  public async refreshStatus(
    options?: InitialPackRequestOptions
  ): Promise<InitialPackStatusDTO | null> {
    if (this.inFlightFetchPromise !== null) {
      return this.inFlightFetchPromise;
    }
    return this.fetchStatusForActivePlayer(options);
  }

  private async fetchStatusForActivePlayer(
    options?: InitialPackRequestOptions
  ): Promise<InitialPackStatusDTO | null> {
    const session = this.getSession();
    if (session === null || session.role !== "PLAYER") {
      return null;
    }

    const requestGeneration = ++this.generation;
    const targetUserId = session.userId;

    this.setState((prev) => ({
      ...prev,
      phase: "LOADING",
      error: null,
      activeUserId: targetUserId,
    }));

    const promise = (async (): Promise<InitialPackStatusDTO | null> => {
      try {
        const response = await fetchInitialPackStatusWithMeta({
          fetchImpl: options?.fetchImpl ?? this.fetchImpl,
          signal: options?.signal,
          tokenProvider: options?.tokenProvider,
          onUnauthorized: options?.onUnauthorized,
        });

        if (this.generation !== requestGeneration) {
          return null;
        }

        this.applyStatusFromGet(response.data, response.correlationId, targetUserId);
        return response.data;
      } catch (error) {
        if (this.generation !== requestGeneration) {
          return null;
        }

        const mappedError = mapInitialPackError(error, "FETCH_STATUS");
        this.setState((prev) => ({
          ...prev,
          phase: "ERROR",
          error: mappedError,
          lastCorrelationId: mappedError.correlationId ?? prev.lastCorrelationId,
          activeUserId: targetUserId,
        }));
        return null;
      } finally {
        if (this.generation === requestGeneration) {
          this.inFlightFetchPromise = null;
        }
      }
    })();

    this.inFlightFetchPromise = promise;
    return promise;
  }

  /**
   * Confirma la apertura del sobre inicial (`POST /api/v1/player/initial-pack/open`).
   *
   * Garantías:
   * - Protege contra doble clic devolviendo la promesa en vuelo si ya se está abriendo.
   * - No emite solicitudes HTTP si el estado actual no permite abrir (`PENDING_CATALOG`,
   *   `COMPLETED`, `REVEALED`, `IDLE` o `LOADING`).
   * - Conserva en `retainedCards` las 15 cartas recibidas previamente en `READY_TO_OPEN`
   *   y pasa a la fase de presentación `REVEALED`.
   * - Si la respuesta del `POST /open` se pierde por error de red o `5xx`, reconcilia
   *   automáticamente con `GET /api/v1/player/initial-pack` antes de declarar fallida la apertura.
   */
  public async openPack(
    options?: InitialPackRequestOptions
  ): Promise<InitialPackStatusDTO | null> {
    if (this.inFlightOpenPromise !== null) {
      return this.inFlightOpenPromise;
    }

    const session = this.getSession();
    if (session === null || session.role !== "PLAYER") {
      return null;
    }

    // Solo permitir apertura cuando el backend confirmó READY_TO_OPEN
    // (ya sea en fase READY_TO_OPEN o reintentando tras un ERROR previo de apertura)
    const canOpen =
      this.state.backendState === "READY_TO_OPEN" &&
      (this.state.phase === "READY_TO_OPEN" || this.state.phase === "ERROR");

    if (!canOpen) {
      return null;
    }

    const requestGeneration = ++this.generation;
    const targetUserId = session.userId;
    const preservedCards = this.state.retainedCards;

    this.setState((prev) => ({
      ...prev,
      phase: "OPENING",
      error: null,
      retainedCards: preservedCards,
      activeUserId: targetUserId,
    }));

    const promise = (async (): Promise<InitialPackStatusDTO | null> => {
      try {
        const response = await openInitialPackWithMeta({
          fetchImpl: options?.fetchImpl ?? this.fetchImpl,
          signal: options?.signal,
          tokenProvider: options?.tokenProvider,
          onUnauthorized: options?.onUnauthorized,
        });

        if (this.generation !== requestGeneration) {
          return null;
        }

        this.loadedForUserId = targetUserId;
        this.setState({
          phase:
            preservedCards.length === INITIAL_COLLECTION_CONSTANTS.REQUIRED_COMMON_CARDS
              ? "REVEALED"
              : "COMPLETED",
          backendState: response.data.state,
          received: response.data.received,
          opened: response.data.opened,
          openedAt: response.data.opened_at,
          retainedCards: preservedCards,
          grantedCubes: INITIAL_COLLECTION_CONSTANTS.GRANTED_CUBES,
          error: null,
          lastCorrelationId: response.correlationId,
          activeUserId: targetUserId,
        });

        return response.data;
      } catch (openError) {
        if (this.generation !== requestGeneration) {
          return null;
        }

        // Regla 10: Si la respuesta del POST se pierde o el resultado es incierto,
        // reconciliar el estado con un GET antes de declarar fallida la apertura.
        if (shouldReconcileAfterOpenFailure(openError)) {
          try {
            const reconciliation = await fetchInitialPackStatusWithMeta({
              fetchImpl: options?.fetchImpl ?? this.fetchImpl,
              signal: options?.signal,
              tokenProvider: options?.tokenProvider,
              onUnauthorized: options?.onUnauthorized,
            });

            if (this.generation !== requestGeneration) {
              return null;
            }

            if (reconciliation.data.state === "COMPLETED" && reconciliation.data.opened) {
              this.loadedForUserId = targetUserId;
              this.setState({
                phase:
                  preservedCards.length === INITIAL_COLLECTION_CONSTANTS.REQUIRED_COMMON_CARDS
                    ? "REVEALED"
                    : "COMPLETED",
                backendState: "COMPLETED",
                received: true,
                opened: true,
                openedAt: reconciliation.data.opened_at,
                retainedCards: preservedCards,
                grantedCubes: INITIAL_COLLECTION_CONSTANTS.GRANTED_CUBES,
                error: null,
                lastCorrelationId: reconciliation.correlationId,
                activeUserId: targetUserId,
              });
              return reconciliation.data;
            }

            if (reconciliation.data.state === "READY_TO_OPEN") {
              const mappedOpenError = mapInitialPackError(openError, "OPEN_PACK");
              this.setState({
                phase: "ERROR",
                backendState: "READY_TO_OPEN",
                received: true,
                opened: false,
                openedAt: null,
                retainedCards: reconciliation.data.cards,
                grantedCubes: INITIAL_COLLECTION_CONSTANTS.GRANTED_CUBES,
                error: mappedOpenError,
                lastCorrelationId:
                  reconciliation.correlationId ?? mappedOpenError.correlationId,
                activeUserId: targetUserId,
              });
              return null;
            }
          } catch (reconcileError) {
            if (this.generation !== requestGeneration) {
              return null;
            }
            // Si la reconciliación detectó 401 (sesión expirada), priorizar el 401
            if (reconcileError instanceof ApiHttpError && reconcileError.status === 401) {
              const mappedAuthError = mapInitialPackError(reconcileError, "OPEN_PACK");
              this.setState((prev) => ({
                ...prev,
                phase: "ERROR",
                retainedCards: preservedCards,
                error: mappedAuthError,
                lastCorrelationId: mappedAuthError.correlationId ?? prev.lastCorrelationId,
              }));
              return null;
            }
          }
        }

        const mappedError = mapInitialPackError(openError, "OPEN_PACK");
        this.setState((prev) => ({
          ...prev,
          phase: "ERROR",
          retainedCards: preservedCards,
          error: mappedError,
          lastCorrelationId: mappedError.correlationId ?? prev.lastCorrelationId,
          activeUserId: targetUserId,
        }));
        return null;
      } finally {
        if (this.generation === requestGeneration) {
          this.inFlightOpenPromise = null;
        }
      }
    })();

    this.inFlightOpenPromise = promise;
    return promise;
  }

  /**
   * Finaliza la vista de revelación (`REVEALED` -> `COMPLETED`) cuando el jugador
   * confirma que revisó sus 15 cartas y desea ingresar al panel principal.
   */
  public completeReveal(): void {
    if (this.state.backendState !== "COMPLETED" || this.state.phase !== "REVEALED") {
      return;
    }

    this.setState((prev) => ({
      ...prev,
      phase: "COMPLETED",
      error: null,
    }));
  }

  /**
   * Limpia el banner de error actual y, si el paquete seguía listo para abrir con las
   * 15 cartas en memoria, restaura la fase `READY_TO_OPEN`.
   */
  public clearError(): void {
    if (this.state.error === null) {
      return;
    }

    this.setState((prev) => ({
      ...prev,
      phase:
        prev.backendState === "READY_TO_OPEN"
          ? "READY_TO_OPEN"
          : prev.backendState === "PENDING_CATALOG"
            ? "PENDING_CATALOG"
            : prev.backendState === "COMPLETED"
              ? "COMPLETED"
              : "IDLE",
      error: null,
    }));
  }
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

/**
 * Hook React para coordinar el flujo de onboarding de colección inicial (US 3.1.1).
 * No contiene JSX ni detalles visuales.
 */
export function useInitialPackOnboarding(options?: {
  readonly controller?: InitialPackOnboardingController;
  readonly fetchImpl?: typeof fetch;
}): UseInitialPackOnboardingResult {
  const controllerRef = useRef<InitialPackOnboardingController | null>(null);
  if (controllerRef.current === null) {
    controllerRef.current =
      options?.controller ??
      new InitialPackOnboardingController({
        fetchImpl: options?.fetchImpl,
      });
  }

  const activeController = options?.controller ?? controllerRef.current;
  const [state, setState] = useState<InitialPackOnboardingState>(() =>
    activeController.getState()
  );

  useEffect(() => {
    const ctrl =
      options?.controller ??
      controllerRef.current ??
      new InitialPackOnboardingController({
        fetchImpl: options?.fetchImpl,
      });

    controllerRef.current = ctrl;
    const unsubscribe = ctrl.subscribe((nextState) => {
      setState(nextState);
    });

    ctrl.start();
    setState(ctrl.getState());

    return () => {
      unsubscribe();
      ctrl.dispose();
    };
  }, [options?.controller, options?.fetchImpl]);

  const openPack = useCallback((requestOptions?: InitialPackRequestOptions) => {
    if (!controllerRef.current) {
      return Promise.resolve(null);
    }
    return controllerRef.current.openPack(requestOptions);
  }, []);

  const refreshStatus = useCallback((requestOptions?: InitialPackRequestOptions) => {
    if (!controllerRef.current) {
      return Promise.resolve(null);
    }
    return controllerRef.current.refreshStatus(requestOptions);
  }, []);

  const completeReveal = useCallback(() => {
    controllerRef.current?.completeReveal();
  }, []);

  const clearError = useCallback(() => {
    controllerRef.current?.clearError();
  }, []);

  const canOpenPack =
    state.backendState === "READY_TO_OPEN" &&
    (state.phase === "READY_TO_OPEN" ||
      (state.phase === "ERROR" && state.error !== null && !state.error.isSessionExpired));

  return {
    ...state,
    isLoading: state.phase === "LOADING",
    isOpening: state.phase === "OPENING",
    isPendingCatalog: state.phase === "PENDING_CATALOG",
    isReadyToOpen: state.phase === "READY_TO_OPEN",
    isRevealed: state.phase === "REVEALED",
    isCompleted: state.phase === "COMPLETED",
    canOpenPack,
    openPack,
    refreshStatus,
    completeReveal,
    clearError,
  };
}
