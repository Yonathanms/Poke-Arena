/**
 * Contratos de autenticación y sesión administrativa para el portal web-admin.
 *
 * Basado en el contrato real de Entrega 1G (`CARD_CREATION_FRONTEND_HANDOFF.md`)
 * y `sesiones_controller.py`. La sesión emitida es agnóstica del proveedor
 * de credenciales (administrador maestro local hoy, Google OIDC en el futuro).
 */

/** Roles de usuario reconocidos por el servicio de sesiones del backend. */
export type PlatformRole = "PLATFORM_ADMIN" | "PLAYER";

/** Proveedores de identidad soportados o previstos por la arquitectura. */
export type AuthProviderKind = "LOCAL" | "GOOGLE";

/**
 * Credenciales de entrada para `POST /api/v1/identity/local/session`.
 * El backend exige `username` de 1 a 63 caracteres y `password` de 1 a 256.
 */
export interface LocalLoginCredentialsDTO {
  readonly username: string;
  readonly password: string;
}

/**
 * Credencial de entrada para `POST /api/v1/identity/google/session`.
 * Se define el contrato para mantener preparado el desacoplamiento del proveedor,
 * sin activar el flujo de Google en esta etapa.
 */
export interface GoogleSessionRequestDTO {
  readonly google_id_token: string;
}

/**
 * Respuesta HTTP 201 de emisión de sesión (`RespuestaSesion` en FastAPI).
 * Compartida por `/api/v1/identity/local/session` y `/api/v1/identity/google/session`.
 */
export interface PlatformSessionResponseDTO {
  readonly access_token: string;
  readonly token_type: "Bearer";
  readonly expires_in: number;
  readonly user_id: string;
  readonly role: PlatformRole;
}

/**
 * Snapshot inmutable de la sesión activa expuesta a los consumidores de la UI.
 * Omite deliberadamente el `access_token` en claro para evitar que componentes
 * visuales registren o filtren la credencial opaca accidentalmente.
 */
export interface ActiveSessionSnapshot {
  readonly userId: string;
  readonly role: PlatformRole;
  readonly expiresAtMs: number;
}

/** Motivos por los cuales una sesión en memoria deja de estar activa. */
export type SessionInvalidationReason = "manual_logout" | "expired" | "unauthorized_401";

/** Evento emitido a los suscriptores cuando cambia el estado de la sesión. */
export interface SessionChangeEvent {
  readonly session: ActiveSessionSnapshot | null;
  readonly reason?: SessionInvalidationReason;
}

/**
 * Estados de alto nivel del ciclo de autenticación en el portal administrativo.
 */
export type AdminAuthStatus =
  | "unauthenticated"
  | "authenticating"
  | "authenticated"
  | "expired";

/**
 * Resultado del cierre de sesión (`DELETE /api/v1/identity/session`).
 * Indica explícitamente si la revocación remota en el servidor pudo verificarse
 * (`204 No Content`), aunque la credencial en memoria siempre se limpia localmente.
 */
export interface LogoutResult {
  readonly localSessionCleared: true;
  readonly remoteRevocationConfirmed: boolean;
  readonly warningMessage: string | null;
  readonly correlationId: string | null;
}
