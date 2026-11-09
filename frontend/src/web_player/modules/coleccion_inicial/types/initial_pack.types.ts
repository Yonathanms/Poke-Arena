/**
 * Contratos TypeScript y estados de onboarding para US 3.1.1 — Recibir Colección Inicial.
 *
 * Basado estrictamente en los contratos verificados del backend:
 * - `backend/src/modules/jugadores/coleccion_mazos/controllers/paquete_inicial_controller.py`
 * - `backend/src/modules/jugadores/coleccion_mazos/domain/entrega_inicial_model.py`
 * - `backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md`
 *
 * Separación arquitectónica obligatoria:
 * 1. `InitialPackState` representa exclusivamente los tres estados persistidos en el backend:
 *    `"PENDING_CATALOG" | "READY_TO_OPEN" | "COMPLETED"`.
 * 2. `InitialPackPresentationPhase` representa el estado de presentación e interacción en el
 *    cliente React (`"IDLE"`, `"LOADING"`, `"PENDING_CATALOG"`, `"READY_TO_OPEN"`, `"OPENING"`,
 *    `"REVEALED"`, `"COMPLETED"`, `"ERROR"`). `"REVEALED"` nunca se interpreta como un estado
 *    del backend: sirve únicamente para presentar las 15 cartas retenidas en memoria justo
 *    después de confirmar la apertura (`POST /open` -> `COMPLETED` con `cards: []`).
 */

/**
 * Estados persistidos y autoritativos del paquete inicial en el backend (`EstadoPaquete`).
 */
export type InitialPackState =
  | "PENDING_CATALOG"
  | "READY_TO_OPEN"
  | "COMPLETED";

/**
 * Resumen público de una carta común incluida en la colección inicial (`CartaInicialDTO`).
 * Solo se devuelve en `GET /api/v1/player/initial-pack` cuando `state === "READY_TO_OPEN"`.
 */
export interface InitialPackCardDTO {
  readonly id: string;
  readonly code: string;
  readonly name: string;
}

/**
 * Contrato HTTP devuelto por:
 * - `GET /api/v1/player/initial-pack` (`200 OK`)
 * - `POST /api/v1/player/initial-pack/open` (`200 OK`)
 */
export interface InitialPackStatusDTO {
  readonly state: InitialPackState;
  readonly received: boolean;
  readonly opened: boolean;
  readonly opened_at: string | null;
  readonly cards: readonly InitialPackCardDTO[];
}

/**
 * Estados de presentación del flujo de onboarding en el cliente React.
 *
 * - `IDLE`: sin sesión de jugador activa (`PLAYER`) o aún no inicializado.
 * - `LOADING`: consultando `GET /api/v1/player/initial-pack`.
 * - `PENDING_CATALOG`: el catálogo tenía menos de 15 cartas comunes elegibles durante el
 *   último login con Google (`received: false`, `opened: false`, `cards: []`).
 * - `READY_TO_OPEN`: colección otorgada pero sobre aún cerrado (`received: true`,
 *   `opened: false`, `cards: [15 cartas]`).
 * - `OPENING`: solicitud `POST /api/v1/player/initial-pack/open` en vuelo (o reconciliando
 *   con `GET /api/v1/player/initial-pack` tras pérdida de respuesta).
 * - `REVEALED`: estado exclusivo de presentación en cliente tras confirmar la apertura en
 *   la sesión actual; muestra las 15 cartas conservadas en memoria antes de pasar al panel.
 * - `COMPLETED`: onboarding finalizado (por ingreso con paquete ya abierto o tras confirmar
 *   la vista de revelación).
 * - `ERROR`: fallo al consultar o abrir el paquete inicial.
 */
export type InitialPackPresentationPhase =
  | "IDLE"
  | "LOADING"
  | "PENDING_CATALOG"
  | "READY_TO_OPEN"
  | "OPENING"
  | "REVEALED"
  | "COMPLETED"
  | "ERROR";

/**
 * Constantes invariantes del dominio de entrega inicial (`entrega_inicial_model.py`).
 */
export const INITIAL_COLLECTION_CONSTANTS = Object.freeze({
  REQUIRED_COMMON_CARDS: 15,
  GRANTED_CUBES: 1000,
});

/**
 * Operación durante la cual se produjo un error en el onboarding.
 */
export type InitialPackFailedOperation = "FETCH_STATUS" | "OPEN_PACK";

/**
 * Error estructurado y normalizado para que la futura capa visual (P2)
 * presente retroalimentación clara sin inspeccionar detalles de transporte HTTP.
 */
export interface InitialPackErrorInfo {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly userGuidance: string;
  readonly correlationId: string | null;
  readonly operation: InitialPackFailedOperation;
  readonly isNetworkError: boolean;
  readonly isSessionExpired: boolean;
  readonly isRetryable: boolean;
}
