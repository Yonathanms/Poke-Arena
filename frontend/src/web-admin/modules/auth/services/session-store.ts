/**
 * Almacén en memoria para la sesión de plataforma (`PLATFORM_ADMIN`).
 *
 * Decisiones de seguridad y arquitectura:
 * 1. El token Bearer opaco se conserva exclusivamente en variables privadas de este
 *    módulo en memoria JS (`Cache-Control: no-store`). Nunca se escribe en
 *    `localStorage`, `sessionStorage`, cookies accesibles por JS ni URLs.
 * 2. Los consumidores visuales reciben únicamente `ActiveSessionSnapshot` (sin el
 *    token en claro), mientras que el cliente HTTP consume un `AccessTokenProvider`
 *    que verifica la expiración antes de cada solicitud.
 * 3. El almacén recibe el DTO estándar `PlatformSessionResponseDTO` sin depender
 *    de cómo se autenticó el usuario (login maestro local en 1G o Google OIDC futuro).
 */

import type {
  ActiveSessionSnapshot,
  PlatformSessionResponseDTO,
  SessionChangeEvent,
  SessionInvalidationReason,
} from "../types/auth.types";

/** Función proveedora del token Bearer actual para inyección en el cliente HTTP. */
export type AccessTokenProvider = () => string | null;

/** Suscriptor reactivo a cambios en el ciclo de vida de la sesión. */
export type SessionListener = (event: SessionChangeEvent) => void;

/** Reloj inyectable para pruebas deterministas de expiración sin usar timers reales. */
export type ClockProvider = () => number;

interface InternalSessionRecord {
  readonly accessToken: string;
  readonly snapshot: ActiveSessionSnapshot;
}

const OPAQUE_BEARER_PATTERN = /^[A-Za-z0-9_-]{43}$/;

let currentRecord: InternalSessionRecord | null = null;
let clock: ClockProvider = () => Date.now();
const listeners = new Set<SessionListener>();

function notifyListeners(event: SessionChangeEvent): void {
  for (const listener of listeners) {
    listener(event);
  }
}

function isExpired(record: InternalSessionRecord, nowMs: number): boolean {
  return nowMs >= record.snapshot.expiresAtMs;
}

/**
 * Verifica si el token cumple el formato opaco emitido por el backend (`token_urlsafe(32)`)
 * o al menos es una cadena ASCII visible no vacía sin espacios.
 */
export function isValidOpaqueBearerFormat(token: string): boolean {
  return OPAQUE_BEARER_PATTERN.test(token);
}

/**
 * Registra en memoria una sesión emitida por el backend (`201 Created`).
 * Si los parámetros son inválidos o el tiempo de vida no es positivo, limpia la sesión.
 */
export function setPlatformSession(sessionDto: PlatformSessionResponseDTO): ActiveSessionSnapshot | null {
  const token = sessionDto.access_token.trim();
  const userId = sessionDto.user_id.trim();
  const expiresInSeconds = sessionDto.expires_in;

  if (!token || !userId || !Number.isFinite(expiresInSeconds) || expiresInSeconds <= 0) {
    clearPlatformSession("manual_logout");
    return null;
  }

  const expiresAtMs = clock() + Math.floor(expiresInSeconds * 1000);
  const snapshot: ActiveSessionSnapshot = Object.freeze({
    userId,
    role: sessionDto.role,
    expiresAtMs,
  });

  currentRecord = {
    accessToken: token,
    snapshot,
  };

  notifyListeners({ session: snapshot });
  return snapshot;
}

/**
 * Limpia el token y metadatos en memoria y notifica a los suscriptores si había
 * una sesión activa o si se solicita explícitamente una invalidación.
 */
export function clearPlatformSession(reason: SessionInvalidationReason = "manual_logout"): void {
  const hadSession = currentRecord !== null;
  currentRecord = null;
  if (hadSession || reason === "unauthorized_401") {
    notifyListeners({ session: null, reason });
  }
}

/**
 * Invalida la sesión cuando el backend responde `401 Unauthorized`.
 */
export function invalidatePlatformSessionOnUnauthorized(): void {
  clearPlatformSession("unauthorized_401");
}

/**
 * Devuelve el token Bearer para uso exclusivo de la capa de transporte HTTP.
 * Si la sesión venció según el reloj actual, la descarta automáticamente y
 * notifica `expired` antes de retornar `null`.
 */
export function getPlatformAccessToken(): string | null {
  if (currentRecord === null) {
    return null;
  }
  if (isExpired(currentRecord, clock())) {
    clearPlatformSession("expired");
    return null;
  }
  return currentRecord.accessToken;
}

/**
 * Devuelve los metadatos públicos de la sesión activa (sin exponer el token).
 * Si la sesión ha expirado, la limpia y retorna `null`.
 */
export function getActiveSessionSnapshot(): ActiveSessionSnapshot | null {
  if (currentRecord === null) {
    return null;
  }
  if (isExpired(currentRecord, clock())) {
    clearPlatformSession("expired");
    return null;
  }
  return currentRecord.snapshot;
}

/**
 * Indica si existe una sesión vigente con el rol `PLATFORM_ADMIN`.
 */
export function hasActivePlatformAdminSession(): boolean {
  const snapshot = getActiveSessionSnapshot();
  return snapshot !== null && snapshot.role === "PLATFORM_ADMIN";
}

/**
 * Registra un suscriptor para cambios de sesión y devuelve una función para cancelar la suscripción.
 */
export function subscribeToSessionChanges(listener: SessionListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Permite inyectar un reloj determinista en pruebas unitarias.
 */
export function configureSessionClockForTests(customClock?: ClockProvider): void {
  clock = customClock ?? (() => Date.now());
}
