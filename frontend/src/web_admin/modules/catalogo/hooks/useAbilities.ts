/**
 * Hook React y controlador reactivo para consultar las habilidades existentes
 * (`GET /api/v1/content/abilities`).
 *
 * Responsabilidades:
 * 1. Consultar el endpoint únicamente cuando existe una sesión activa con rol `PLATFORM_ADMIN`.
 * 2. Deduplicar peticiones en vuelo para el mismo administrador (evitando llamadas dobles
 *    bajo React StrictMode).
 * 3. Cancelar o ignorar respuestas tardías si la sesión se cierra, expira, cambia de
 *    usuario o se inicia un reintento manual.
 * 4. Limpiar inmediatamente la lista en memoria al invalidarse o cerrarse la sesión para
 *    no mostrar datos de una sesión anterior.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import {
  getActiveSessionSnapshot,
  subscribeToSessionChanges,
} from "../../auth/services/session-store";
import type { ActiveSessionSnapshot } from "../../auth/types/auth.types";
import {
  fetchSelectableAbilities,
  type CatalogServiceRequestOptions,
} from "../services/catalog.api";
import type { AbilityOptionDTO } from "../types/card-admin.types";

/** Error estructurado de la carga de habilidades para presentación en UI. */
export interface AbilitiesErrorInfo {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly correlationId: string | null;
}

/** Estado inmutable de la consulta de habilidades. */
export interface AbilitiesQueryState {
  readonly abilities: readonly AbilityOptionDTO[];
  readonly isLoading: boolean;
  readonly hasLoaded: boolean;
  readonly isEmpty: boolean;
  readonly error: AbilitiesErrorInfo | null;
}

export interface UseAbilitiesResult extends AbilitiesQueryState {
  readonly reload: () => Promise<readonly AbilityOptionDTO[]>;
}

const INITIAL_QUERY_STATE: AbilitiesQueryState = Object.freeze({
  abilities: Object.freeze([]),
  isLoading: false,
  hasLoaded: false,
  isEmpty: false,
  error: null,
});

function toAbilitiesErrorInfo(error: unknown): AbilitiesErrorInfo {
  if (error instanceof ApiHttpError) {
    return {
      status: error.status,
      code: error.code,
      detail: error.detail,
      correlationId: error.correlationId,
    };
  }
  return {
    status: 500,
    code: "error_carga_habilidades",
    detail: "No se pudo consultar el catálogo de habilidades.",
    correlationId: null,
  };
}

function isAuthorizedAdmin(session: ActiveSessionSnapshot | null): session is ActiveSessionSnapshot {
  return session !== null && session.role === "PLATFORM_ADMIN";
}

/**
 * Controlador determinista del ciclo de vida de la consulta de habilidades.
 * Permite probar todas las transiciones asíncronas, cancelaciones, cambios de sesión
 * y respuestas tardías sin acoplarse al temporizador de renderizado.
 */
export class AbilitiesQueryController {
  private readonly getSession: () => ActiveSessionSnapshot | null;
  private readonly subscribeSession: (
    listener: (event: { readonly session: ActiveSessionSnapshot | null }) => void
  ) => () => void;
  private readonly fetchImpl?: typeof fetch;

  private state: AbilitiesQueryState = INITIAL_QUERY_STATE;
  private readonly listeners = new Set<(state: AbilitiesQueryState) => void>();
  private requestGeneration = 0;
  private activeAbortController: AbortController | null = null;
  private inFlightPromise: Promise<readonly AbilityOptionDTO[]> | null = null;
  private inFlightUserId: string | null = null;
  private loadedForUserId: string | null = null;
  private unsubscribeSession: (() => void) | null = null;

  constructor(options?: {
    readonly getSession?: () => ActiveSessionSnapshot | null;
    readonly subscribeSession?: (
      listener: (event: { readonly session: ActiveSessionSnapshot | null }) => void
    ) => () => void;
    readonly fetchImpl?: typeof fetch;
  }) {
    this.getSession = options?.getSession ?? getActiveSessionSnapshot;
    this.subscribeSession = options?.subscribeSession ?? subscribeToSessionChanges;
    this.fetchImpl = options?.fetchImpl;
  }

  public getState(): AbilitiesQueryState {
    return this.state;
  }

  public subscribe(listener: (state: AbilitiesQueryState) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private setState(next: AbilitiesQueryState): void {
    this.state = Object.freeze(next);
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }

  private cancelInFlight(): void {
    this.requestGeneration += 1;
    if (this.activeAbortController) {
      this.activeAbortController.abort();
      this.activeAbortController = null;
    }
    this.inFlightPromise = null;
    this.inFlightUserId = null;
  }

  /**
   * Inicia la escucha de cambios de sesión y dispara la carga inicial si ya hay
   * un administrador autenticado.
   */
  public start(): void {
    if (!this.unsubscribeSession) {
      this.unsubscribeSession = this.subscribeSession(({ session }) => {
        this.handleSessionTransition(session);
      });
    }
    this.handleSessionTransition(this.getSession());
  }

  /**
   * Cancela cualquier solicitud en vuelo y libera la suscripción al almacén de sesión.
   */
  public dispose(): void {
    this.cancelInFlight();
    if (this.unsubscribeSession) {
      this.unsubscribeSession();
      this.unsubscribeSession = null;
    }
  }

  private handleSessionTransition(session: ActiveSessionSnapshot | null): void {
    if (!isAuthorizedAdmin(session)) {
      this.cancelInFlight();
      this.loadedForUserId = null;
      if (
        this.state.abilities.length > 0 ||
        this.state.isLoading ||
        this.state.hasLoaded ||
        this.state.error !== null
      ) {
        this.setState(INITIAL_QUERY_STATE);
      }
      return;
    }

    // Si cambió la identidad del administrador, limpiamos los datos del usuario anterior y recargamos
    if (this.loadedForUserId !== null && this.loadedForUserId !== session.userId) {
      this.cancelInFlight();
      this.loadedForUserId = null;
      this.setState(INITIAL_QUERY_STATE);
    }

    if (this.loadedForUserId === session.userId && this.state.hasLoaded) {
      return;
    }

    if (this.inFlightPromise && this.inFlightUserId === session.userId) {
      return;
    }

    void this.load({ force: false });
  }

  /**
   * Ejecuta o reutiliza la consulta de habilidades para la sesión administrativa actual.
   */
  public async load(options?: { readonly force?: boolean }): Promise<readonly AbilityOptionDTO[]> {
    const session = this.getSession();
    if (!isAuthorizedAdmin(session)) {
      this.cancelInFlight();
      this.loadedForUserId = null;
      this.setState(INITIAL_QUERY_STATE);
      return INITIAL_QUERY_STATE.abilities;
    }

    const force = options?.force ?? true;
    if (!force && this.inFlightPromise && this.inFlightUserId === session.userId) {
      return this.inFlightPromise;
    }

    this.cancelInFlight();
    const currentGeneration = this.requestGeneration;
    const targetUserId = session.userId;
    const abortController = new AbortController();
    this.activeAbortController = abortController;
    this.inFlightUserId = targetUserId;

    this.setState({
      abilities: this.loadedForUserId === targetUserId ? this.state.abilities : Object.freeze([]),
      isLoading: true,
      hasLoaded: this.loadedForUserId === targetUserId ? this.state.hasLoaded : false,
      isEmpty: false,
      error: null,
    });

    const promise = (async (): Promise<readonly AbilityOptionDTO[]> => {
      try {
        const items = await fetchSelectableAbilities({
          fetchImpl: this.fetchImpl,
          signal: abortController.signal,
        });

        // Verificar que esta respuesta sigue correspondiendo a la generación y sesión activas
        const currentSession = this.getSession();
        if (
          currentGeneration !== this.requestGeneration ||
          !isAuthorizedAdmin(currentSession) ||
          currentSession.userId !== targetUserId
        ) {
          return INITIAL_QUERY_STATE.abilities;
        }

        this.loadedForUserId = targetUserId;
        this.setState({
          abilities: items,
          isLoading: false,
          hasLoaded: true,
          isEmpty: items.length === 0,
          error: null,
        });
        return items;
      } catch (error) {
        const currentSession = this.getSession();
        if (
          currentGeneration !== this.requestGeneration ||
          !isAuthorizedAdmin(currentSession) ||
          currentSession.userId !== targetUserId
        ) {
          return INITIAL_QUERY_STATE.abilities;
        }

        this.setState({
          abilities: Object.freeze([]),
          isLoading: false,
          hasLoaded: false,
          isEmpty: false,
          error: toAbilitiesErrorInfo(error),
        });
        return INITIAL_QUERY_STATE.abilities;
      } finally {
        if (currentGeneration === this.requestGeneration) {
          this.activeAbortController = null;
          this.inFlightPromise = null;
          this.inFlightUserId = null;
        }
      }
    })();

    this.inFlightPromise = promise;
    return promise;
  }
}

/**
 * Hook React para consultar habilidades del catálogo cuando existe sesión administrativa.
 */
export function useAbilities(options?: CatalogServiceRequestOptions): UseAbilitiesResult {
  const controllerRef = useRef<AbilitiesQueryController | null>(null);
  if (controllerRef.current === null) {
    controllerRef.current = new AbilitiesQueryController({
      fetchImpl: options?.fetchImpl,
    });
  }

  const [state, setState] = useState<AbilitiesQueryState>(() =>
    controllerRef.current ? controllerRef.current.getState() : INITIAL_QUERY_STATE
  );

  useEffect(() => {
    const controller = new AbilitiesQueryController({
      fetchImpl: options?.fetchImpl,
    });
    controllerRef.current = controller;

    const unsubscribe = controller.subscribe((nextState) => {
      setState(nextState);
    });
    controller.start();

    return () => {
      unsubscribe();
      controller.dispose();
    };
  }, [options?.fetchImpl]);

  const reload = useCallback((): Promise<readonly AbilityOptionDTO[]> => {
    if (!controllerRef.current) {
      return Promise.resolve(INITIAL_QUERY_STATE.abilities);
    }
    return controllerRef.current.load({ force: true });
  }, []);

  return {
    abilities: state.abilities,
    isLoading: state.isLoading,
    hasLoaded: state.hasLoaded,
    isEmpty: state.isEmpty,
    error: state.error,
    reload,
  };
}
