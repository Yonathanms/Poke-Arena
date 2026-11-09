/**
 * Servicio especializado de autenticación para el portal administrativo (`web_admin`).
 *
 * Responsabilidades:
 * 1. Conectar los hooks de sesión en memoria (`session-store.ts`) con el cliente HTTP
 *    transversal (`http-client.ts`) una sola vez y de forma idempotente.
 * 2. Ejecutar el inicio de sesión del administrador maestro local contra
 *    `POST /api/v1/identity/local/session`, validando estrictamente la estructura de
 *    la respuesta (`201 Created`) y exigiendo el rol `PLATFORM_ADMIN`.
 * 3. Gestionar el cierre de sesión contra `DELETE /api/v1/identity/session` (`204 No Content`),
 *    limpiando siempre la sesión en memoria e informando si la revocación remota no pudo
 *    confirmarse (por fallo de red o indisponibilidad).
 * 4. Separar la activación de la sesión de plataforma (`activatePlatformAdminSession`) del
 *    proveedor de credenciales para facilitar la futura incorporación de Google OIDC.
 */

import {
  ApiHttpError,
  configureHttpClientSessionHooks,
  requestApi,
  requestApiWithMeta,
} from "../../../../shared/services/http-client";
import type {
  ActiveSessionSnapshot,
  LocalLoginCredentialsDTO,
  LogoutResult,
  PlatformSessionResponseDTO,
} from "../types/auth.types";
import {
  clearPlatformSession,
  getPlatformAccessToken,
  invalidatePlatformSessionOnUnauthorized,
  isValidOpaqueBearerFormat,
  setPlatformSession,
} from "./session-store";

const LOCAL_SESSION_ENDPOINT = "/identity/local/session";
const REVOKE_SESSION_ENDPOINT = "/identity/session";

const USERNAME_MIN_LENGTH = 1;
const USERNAME_MAX_LENGTH = 63;
const PASSWORD_MIN_LENGTH = 1;
const PASSWORD_MAX_LENGTH = 256;

let httpHooksInitialized = false;

/** Opciones de inyección para pruebas unitarias sin tocar la red real. */
export interface AuthServiceRequestOptions {
  readonly fetchImpl?: typeof fetch;
  readonly signal?: AbortSignal;
}

/**
 * Conecta `http-client.ts` con `session-store.ts` de manera idempotente.
 * Se invoca automáticamente al usar `auth.api.ts`, evitando configuraciones
 * repetidas en cada render de React.
 */
export function ensureAuthHttpBridgeConfigured(): void {
  if (httpHooksInitialized) {
    return;
  }
  configureHttpClientSessionHooks({
    getAccessToken: getPlatformAccessToken,
    onUnauthorized: invalidatePlatformSessionOnUnauthorized,
  });
  httpHooksInitialized = true;
}

/**
 * Valida las restricciones de entrada del endpoint local (`CredencialLocal` en FastAPI)
 * antes de enviar la solicitud por la red. Nunca incluye la contraseña en mensajes de error.
 */
export function validateLocalLoginInput(credentials: LocalLoginCredentialsDTO): string | null {
  const username = credentials.username.trim();
  const password = credentials.password;

  if (username.length < USERNAME_MIN_LENGTH) {
    return "Ingresa el nombre de usuario del administrador.";
  }
  if (username.length > USERNAME_MAX_LENGTH) {
    return `El usuario no puede exceder ${USERNAME_MAX_LENGTH} caracteres.`;
  }
  if (password.length < PASSWORD_MIN_LENGTH) {
    return "Ingresa la contraseña del administrador.";
  }
  if (password.length > PASSWORD_MAX_LENGTH) {
    return `La contraseña no puede exceder ${PASSWORD_MAX_LENGTH} caracteres.`;
  }
  return null;
}

function isPlatformSessionResponseDTO(payload: unknown): payload is PlatformSessionResponseDTO {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }
  const candidate = payload as Record<string, unknown>;
  return (
    typeof candidate.access_token === "string" &&
    isValidOpaqueBearerFormat(candidate.access_token) &&
    candidate.token_type === "Bearer" &&
    typeof candidate.expires_in === "number" &&
    Number.isFinite(candidate.expires_in) &&
    candidate.expires_in > 0 &&
    typeof candidate.user_id === "string" &&
    candidate.user_id.trim().length > 0 &&
    (candidate.role === "PLATFORM_ADMIN" || candidate.role === "PLAYER")
  );
}

/**
 * Revoca silenciosamente en segundo plano un token válido cuyo rol no sea `PLATFORM_ADMIN`
 * para no dejar sesiones huérfanas activas en el servidor.
 */
async function revokeUnprivilegedTokenBestEffort(
  token: string,
  options?: AuthServiceRequestOptions
): Promise<void> {
  try {
    await requestApi<undefined>(REVOKE_SESSION_ENDPOINT, {
      method: "DELETE",
      requiresAuth: false,
      headers: { Authorization: `Bearer ${token}` },
      fetchImpl: options?.fetchImpl,
      signal: options?.signal,
    });
  } catch {
    // El rechazo principal es el 403 local por rol insuficiente; la revocación es best-effort.
  }
}

/**
 * Valida una respuesta de sesión de plataforma (proveniente de login local hoy o
 * de otro proveedor en el futuro), exige el rol `PLATFORM_ADMIN` y la registra en
 * memoria devolviendo únicamente el snapshot público sin el token en claro.
 */
export async function activatePlatformAdminSession(
  rawPayload: unknown,
  correlationId: string | null = null,
  options?: AuthServiceRequestOptions
): Promise<ActiveSessionSnapshot> {
  ensureAuthHttpBridgeConfigured();

  if (!isPlatformSessionResponseDTO(rawPayload)) {
    clearPlatformSession("manual_logout");
    throw new ApiHttpError({
      status: 502,
      code: "respuesta_sesion_invalida",
      detail: "El servidor devolvió un contrato de sesión inválido.",
      title: "Bad Gateway",
      correlationId,
    });
  }

  if (rawPayload.role !== "PLATFORM_ADMIN") {
    clearPlatformSession("manual_logout");
    await revokeUnprivilegedTokenBestEffort(rawPayload.access_token, options);
    throw new ApiHttpError({
      status: 403,
      code: "permiso_denegado",
      detail: "La cuenta autenticada no posee el rol requerido PLATFORM_ADMIN.",
      title: "Forbidden",
      correlationId,
    });
  }

  const snapshot = setPlatformSession(rawPayload);
  if (!snapshot) {
    throw new ApiHttpError({
      status: 502,
      code: "respuesta_sesion_invalida",
      detail: "No fue posible inicializar la sesión administrativa.",
      title: "Bad Gateway",
      correlationId,
    });
  }

  return snapshot;
}

/**
 * Autentica al administrador maestro local mediante `POST /api/v1/identity/local/session`.
 * No almacena la contraseña y solo expone `ActiveSessionSnapshot`.
 */
export async function loginWithLocalMasterAdmin(
  credentials: LocalLoginCredentialsDTO,
  options?: AuthServiceRequestOptions
): Promise<ActiveSessionSnapshot> {
  ensureAuthHttpBridgeConfigured();

  const validationError = validateLocalLoginInput(credentials);
  if (validationError) {
    throw new ApiHttpError({
      status: 422,
      code: "credenciales_incompletas",
      detail: validationError,
      title: "Unprocessable Entity",
    });
  }

  const response = await requestApiWithMeta<unknown>(LOCAL_SESSION_ENDPOINT, {
    method: "POST",
    requiresAuth: false,
    body: {
      username: credentials.username.trim(),
      password: credentials.password,
    },
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
  });

  return activatePlatformAdminSession(response.data, response.correlationId, options);
}

/**
 * Inicia sesión mediante Google OIDC (`POST /api/v1/identity/login/google`).
 * Acepta tanto jugadores como administradores, inicializa la sesión en memoria
 * y devuelve el snapshot inmutable.
 */
export async function loginWithGoogleIdToken(
  idToken: string,
  options?: AuthServiceRequestOptions
): Promise<ActiveSessionSnapshot> {
  ensureAuthHttpBridgeConfigured();

  const response = await requestApiWithMeta<PlatformSessionResponseDTO>("/identity/login/google", {
    method: "POST",
    requiresAuth: false,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
  });

  const snapshot = setPlatformSession(response.data);
  if (!snapshot) {
    throw new ApiHttpError({
      status: 502,
      code: "respuesta_sesion_invalida",
      detail: "No fue posible inicializar la sesión de usuario.",
      title: "Bad Gateway",
      correlationId: response.correlationId,
    });
  }

  return snapshot;
}

/**
 * Cierra la sesión actual invocando `DELETE /api/v1/identity/session` (`204 No Content`)
 * y limpiando inmediatamente el estado en memoria.
 *
 * Si la solicitud de revocación falla por red o error del servidor, limpia igualmente
 * la sesión local y devuelve `remoteRevocationConfirmed: false` con una advertencia
 * explícita para no presentar la revocación remota como verificada.
 */
export async function logoutPlatformSession(
  options?: AuthServiceRequestOptions
): Promise<LogoutResult> {
  ensureAuthHttpBridgeConfigured();

  const activeToken = getPlatformAccessToken();
  clearPlatformSession("manual_logout");

  if (!activeToken) {
    return {
      localSessionCleared: true,
      remoteRevocationConfirmed: true,
      warningMessage: null,
      correlationId: null,
    };
  }

  try {
    const response = await requestApiWithMeta<undefined>(REVOKE_SESSION_ENDPOINT, {
      method: "DELETE",
      requiresAuth: false,
      headers: { Authorization: `Bearer ${activeToken}` },
      fetchImpl: options?.fetchImpl,
      signal: options?.signal,
    });

    return {
      localSessionCleared: true,
      remoteRevocationConfirmed: response.status === 204,
      warningMessage: null,
      correlationId: response.correlationId,
    };
  } catch (error) {
    const correlationId = error instanceof ApiHttpError ? error.correlationId : null;
    return {
      localSessionCleared: true,
      remoteRevocationConfirmed: false,
      warningMessage:
        "Se cerró la sesión en este navegador, pero no se pudo confirmar la revocación en el servidor.",
      correlationId,
    };
  }
}
