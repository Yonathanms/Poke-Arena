/**
 * Hook reactivo que sincroniza el almacén de sesión (`session-store.ts`) y el
 * servicio de autenticación (`auth.api.ts`) con los componentes de React.
 *
 * Garantías:
 * 1. Nunca expone el `access_token` en claro a la capa visual; devuelve solo
 *    `ActiveSessionSnapshot` y banderas derivadas.
 * 2. Calcula el estado único (`unauthenticated`, `authenticating`, `authenticated`, `expired`)
 *    sin duplicar fuentes de verdad contradictorias.
 * 3. Vigila el tiempo restante (`remainingSeconds`) y dispara la invalidación exacta
 *    cuando vence `expiresAtMs`, limpiando todos los timers al desmontar.
 * 4. Bloquea envíos concurrentes de login/logout mediante una bandera sincrónica (`useRef`).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import {
  ensureAuthHttpBridgeConfigured,
  loginWithLocalMasterAdmin,
  logoutPlatformSession,
  type AuthServiceRequestOptions,
} from "../services/auth.api";
import {
  getActiveSessionSnapshot,
  subscribeToSessionChanges,
} from "../services/session-store";
import type {
  ActiveSessionSnapshot,
  AdminAuthStatus,
  LocalLoginCredentialsDTO,
  LogoutResult,
  SessionInvalidationReason,
} from "../types/auth.types";

/** Error estructurado listo para presentarse en la interfaz de autenticación. */
export interface AdminAuthErrorInfo {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly correlationId: string | null;
  readonly retryAfterSeconds: number | null;
}

export interface UseAdminSessionResult {
  readonly status: AdminAuthStatus;
  readonly session: ActiveSessionSnapshot | null;
  readonly isAuthenticated: boolean;
  readonly isAdminAuthenticated: boolean;
  readonly isPlayerAuthenticated: boolean;
  readonly isAuthenticating: boolean;
  readonly isLoggingOut: boolean;
  readonly remainingSeconds: number;
  readonly retryCooldownSeconds: number;
  readonly authError: AdminAuthErrorInfo | null;
  readonly logoutNotice: string | null;
  readonly lastInvalidationReason: SessionInvalidationReason | null;
  readonly loginLocal: (
    credentials: LocalLoginCredentialsDTO,
    options?: AuthServiceRequestOptions
  ) => Promise<boolean>;
  readonly logout: (options?: AuthServiceRequestOptions) => Promise<LogoutResult>;
  readonly clearAuthFeedback: () => void;
}

/**
 * Traduce un error HTTP o de validación de login en un mensaje claro para el administrador,
 * distinguiendo explícitamente `401`, `403`, `404` (login local deshabilitado), `429` y `500/503`.
 */
export function mapAuthErrorToUserInfo(error: unknown): AdminAuthErrorInfo {
  if (error instanceof ApiHttpError) {
    if (error.status === 401) {
      return {
        status: 401,
        code: error.code,
        title: "Credenciales inválidas",
        detail: "El usuario o la contraseña no son correctos. Verifica tus datos e inténtalo de nuevo.",
        correlationId: error.correlationId,
        retryAfterSeconds: null,
      };
    }
    if (error.status === 403) {
      return {
        status: 403,
        code: error.code,
        title: "Permisos insuficientes",
        detail: "Tu cuenta no cuenta con el rol requerido PLATFORM_ADMIN para acceder a este portal.",
        correlationId: error.correlationId,
        retryAfterSeconds: null,
      };
    }
    if (error.status === 404) {
      return {
        status: 404,
        code: error.code,
        title: "Autenticación local no disponible",
        detail:
          "El inicio de sesión de administrador local está deshabilitado en el servidor actual (IDENTITY_LOCAL_ENABLED=false).",
        correlationId: error.correlationId,
        retryAfterSeconds: null,
      };
    }
    if (error.status === 429) {
      const waitSecs = error.retryAfterSeconds;
      const waitDetail =
        waitSecs !== null && waitSecs > 0
          ? `Se alcanzó el límite temporal de intentos. Espera ${waitSecs} segundos antes de volver a intentarlo.`
          : "Se alcanzó el límite temporal de intentos. Espera unos segundos antes de volver a intentarlo.";
      return {
        status: 429,
        code: error.code,
        title: "Demasiados intentos de inicio de sesión",
        detail: waitDetail,
        correlationId: error.correlationId,
        retryAfterSeconds: waitSecs,
      };
    }
    if (error.isNetworkError) {
      return {
        status: 0,
        code: error.code,
        title: "Sin conexión con el servidor",
        detail: error.detail,
        correlationId: null,
        retryAfterSeconds: null,
      };
    }
    if (error.status >= 500) {
      return {
        status: error.status,
        code: error.code,
        title: "Servicio de identidad no disponible",
        detail: error.detail,
        correlationId: error.correlationId,
        retryAfterSeconds: null,
      };
    }
    return {
      status: error.status,
      code: error.code,
      title: "Datos de acceso inválidos",
      detail: error.detail,
      correlationId: error.correlationId,
      retryAfterSeconds: null,
    };
  }

  return {
    status: 500,
    code: "error_inesperado",
    title: "Error inesperado",
    detail: "No se pudo procesar el inicio de sesión.",
    correlationId: null,
    retryAfterSeconds: null,
  };
}

function computeRemainingSeconds(snapshot: ActiveSessionSnapshot | null): number {
  if (!snapshot) {
    return 0;
  }
  return Math.max(0, Math.ceil((snapshot.expiresAtMs - Date.now()) / 1000));
}

export function useAdminSession(): UseAdminSessionResult {
  ensureAuthHttpBridgeConfigured();

  const [session, setSession] = useState<ActiveSessionSnapshot | null>(() =>
    getActiveSessionSnapshot()
  );
  const [lastInvalidationReason, setLastInvalidationReason] =
    useState<SessionInvalidationReason | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [authError, setAuthError] = useState<AdminAuthErrorInfo | null>(null);
  const [logoutNotice, setLogoutNotice] = useState<string | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(() =>
    computeRemainingSeconds(getActiveSessionSnapshot())
  );
  const [retryCooldownSeconds, setRetryCooldownSeconds] = useState<number>(0);

  const inFlightLoginRef = useRef(false);
  const inFlightLogoutRef = useRef(false);

  // Suscripción única al almacén en memoria con limpieza garantizada
  useEffect(() => {
    setSession(getActiveSessionSnapshot());

    const unsubscribe = subscribeToSessionChanges((event) => {
      setSession(event.session);
      setRemainingSeconds(computeRemainingSeconds(event.session));
      if (event.session !== null) {
        setLastInvalidationReason(null);
      } else if (event.reason) {
        setLastInvalidationReason(event.reason);
      }
    });

    return unsubscribe;
  }, []);

  // Temporizador de expiración de la sesión activa (se limpia automáticamente al cambiar o desmontar)
  useEffect(() => {
    if (!session) {
      setRemainingSeconds(0);
      return undefined;
    }

    const syncClock = (): void => {
      const active = getActiveSessionSnapshot();
      if (!active) {
        setRemainingSeconds(0);
        return;
      }
      setRemainingSeconds(computeRemainingSeconds(active));
    };

    syncClock();
    const intervalId = window.setInterval(syncClock, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [session]);

  // Cuenta regresiva accesible para bloqueos 429 (Retry-After)
  useEffect(() => {
    if (retryCooldownSeconds <= 0) {
      return undefined;
    }
    const timerId = window.setInterval(() => {
      setRetryCooldownSeconds((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => {
      window.clearInterval(timerId);
    };
  }, [retryCooldownSeconds]);

  const clearAuthFeedback = useCallback((): void => {
    setAuthError(null);
    setLogoutNotice(null);
  }, []);

  const loginLocal = useCallback(
    async (
      credentials: LocalLoginCredentialsDTO,
      options?: AuthServiceRequestOptions
    ): Promise<boolean> => {
      if (inFlightLoginRef.current || retryCooldownSeconds > 0) {
        return false;
      }

      inFlightLoginRef.current = true;
      setIsAuthenticating(true);
      setAuthError(null);
      setLogoutNotice(null);

      try {
        await loginWithLocalMasterAdmin(credentials, options);
        return true;
      } catch (error) {
        const mapped = mapAuthErrorToUserInfo(error);
        setAuthError(mapped);
        if (mapped.status === 429 && mapped.retryAfterSeconds && mapped.retryAfterSeconds > 0) {
          setRetryCooldownSeconds(mapped.retryAfterSeconds);
        }
        return false;
      } finally {
        inFlightLoginRef.current = false;
        setIsAuthenticating(false);
      }
    },
    [retryCooldownSeconds]
  );

  const logout = useCallback(
    async (options?: AuthServiceRequestOptions): Promise<LogoutResult> => {
      if (inFlightLogoutRef.current) {
        return {
          localSessionCleared: true,
          remoteRevocationConfirmed: false,
          warningMessage: null,
          correlationId: null,
        };
      }

      inFlightLogoutRef.current = true;
      setIsLoggingOut(true);
      setAuthError(null);

      // Deshabilitar auto-select de Google para que el siguiente inicio solicite cuenta limpia
      if (typeof window !== "undefined" && window.google?.accounts?.id) {
        try {
          window.google.accounts.id.disableAutoSelect();
        } catch {
          // Ignorar si el SDK de Google no está disponible
        }
      }

      try {
        const result = await logoutPlatformSession(options);
        if (result.warningMessage) {
          setLogoutNotice(result.warningMessage);
        } else {
          setLogoutNotice("Sesión cerrada correctamente.");
        }
        return result;
      } finally {
        inFlightLogoutRef.current = false;
        setIsLoggingOut(false);
      }
    },
    []
  );

  const isAuthenticated = session !== null;
  const isAdminAuthenticated = session !== null && session.role === "PLATFORM_ADMIN";
  const isPlayerAuthenticated = session !== null && session.role === "PLAYER";

  let status: AdminAuthStatus = "unauthenticated";
  if (isAuthenticating) {
    status = "authenticating";
  } else if (isAdminAuthenticated) {
    status = "authenticated";
  } else if (
    lastInvalidationReason === "expired" ||
    lastInvalidationReason === "unauthorized_401"
  ) {
    status = "expired";
  }

  return {
    status,
    session,
    isAuthenticated,
    isAdminAuthenticated,
    isPlayerAuthenticated,
    isAuthenticating,
    isLoggingOut,
    remainingSeconds,
    retryCooldownSeconds,
    authError,
    logoutNotice,
    lastInvalidationReason,
    loginLocal,
    logout,
    clearAuthFeedback,
  };
}
