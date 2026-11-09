/**
 * Servicio HTTP para el paquete inicial de jugador (`web_player` — US 3.1.1).
 *
 * Responsabilidades:
 * 1. Consultar el estado autoritativo de la colección inicial mediante
 *    `GET /api/v1/player/initial-pack` (`fetchInitialPackStatus`).
 * 2. Confirmar la apertura idempotente del sobre inicial mediante
 *    `POST /api/v1/player/initial-pack/open` (`openInitialPack`), sin enviar
 *    `user_id`, cartas, cubos ni ningún campo de negocio o query string.
 * 3. Reutilizar `http-client.ts` y el puente de sesión en memoria (`auth.api.ts`)
 *    para adjuntar el token Bearer opaco de Poké-Arena y normalizar errores RFC 7807.
 * 4. Validar estrictamente el contrato `InitialPackStatusDTO` devuelto por FastAPI
 *    y congelar las estructuras resultantes para garantizar inmutabilidad.
 */

import {
  ApiHttpError,
  requestApiWithMeta,
  type ApiResponse,
  type HttpAccessTokenProvider,
  type HttpUnauthorizedHandler,
} from "../../../../shared/services/http-client";
import { ensureAuthHttpBridgeConfigured } from "../../../../web_admin/modules/auth/services/auth.api";
import {
  INITIAL_COLLECTION_CONSTANTS,
  type InitialPackCardDTO,
  type InitialPackState,
  type InitialPackStatusDTO,
} from "../types/initial_pack.types";

const INITIAL_PACK_STATUS_ENDPOINT = "/player/initial-pack";
const INITIAL_PACK_OPEN_ENDPOINT = "/player/initial-pack/open";

/** Opciones de solicitud inyectables para pruebas unitarias y cancelación. */
export interface InitialPackRequestOptions {
  readonly fetchImpl?: typeof fetch;
  readonly signal?: AbortSignal;
  readonly tokenProvider?: HttpAccessTokenProvider;
  readonly onUnauthorized?: HttpUnauthorizedHandler;
}

function isInitialPackState(value: unknown): value is InitialPackState {
  return (
    value === "PENDING_CATALOG" ||
    value === "READY_TO_OPEN" ||
    value === "COMPLETED"
  );
}

function isInitialPackCardDTO(item: unknown): item is InitialPackCardDTO {
  if (typeof item !== "object" || item === null) {
    return false;
  }
  const candidate = item as Record<string, unknown>;
  return (
    typeof candidate.id === "string" &&
    candidate.id.trim().length > 0 &&
    typeof candidate.code === "string" &&
    candidate.code.trim().length > 0 &&
    typeof candidate.name === "string" &&
    candidate.name.trim().length > 0
  );
}

/**
 * Verifica que el payload cumpla el contrato `PaqueteInicialDTO` de FastAPI y
 * las invariantes de negocio de cada uno de los tres estados persistidos.
 */
export function isInitialPackStatusDTO(payload: unknown): payload is InitialPackStatusDTO {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }

  const candidate = payload as Record<string, unknown>;
  if (!isInitialPackState(candidate.state)) {
    return false;
  }
  if (typeof candidate.received !== "boolean" || typeof candidate.opened !== "boolean") {
    return false;
  }
  if (
    candidate.opened_at !== null &&
    (typeof candidate.opened_at !== "string" || candidate.opened_at.trim().length === 0)
  ) {
    return false;
  }
  if (!Array.isArray(candidate.cards) || !candidate.cards.every(isInitialPackCardDTO)) {
    return false;
  }

  if (candidate.state === "PENDING_CATALOG") {
    return (
      candidate.received === false &&
      candidate.opened === false &&
      candidate.opened_at === null &&
      candidate.cards.length === 0
    );
  }

  if (candidate.state === "READY_TO_OPEN") {
    if (
      candidate.received !== true ||
      candidate.opened !== false ||
      candidate.opened_at !== null ||
      candidate.cards.length !== INITIAL_COLLECTION_CONSTANTS.REQUIRED_COMMON_CARDS
    ) {
      return false;
    }
    const uniqueIds = new Set(candidate.cards.map((card) => card.id));
    return uniqueIds.size === INITIAL_COLLECTION_CONSTANTS.REQUIRED_COMMON_CARDS;
  }

  // state === "COMPLETED"
  return (
    candidate.received === true &&
    candidate.opened === true &&
    typeof candidate.opened_at === "string" &&
    candidate.cards.length === 0
  );
}

function freezeInitialPackStatus(dto: InitialPackStatusDTO): InitialPackStatusDTO {
  const frozenCards = Object.freeze(
    dto.cards.map((card) =>
      Object.freeze({
        id: card.id,
        code: card.code,
        name: card.name,
      })
    )
  );

  return Object.freeze({
    state: dto.state,
    received: dto.received,
    opened: dto.opened,
    opened_at: dto.opened_at,
    cards: frozenCards,
  });
}

function validateAndFreezeResponse(
  response: ApiResponse<unknown>
): ApiResponse<InitialPackStatusDTO> {
  if (!isInitialPackStatusDTO(response.data)) {
    throw new ApiHttpError({
      status: 502,
      code: "respuesta_paquete_invalida",
      detail: "El servidor devolvió un contrato de paquete inicial inválido o inconsistente.",
      title: "Bad Gateway",
      correlationId: response.correlationId,
    });
  }

  return {
    status: response.status,
    data: freezeInitialPackStatus(response.data),
    correlationId: response.correlationId,
  };
}

/**
 * Consulta el estado actual del paquete inicial (`GET /api/v1/player/initial-pack`)
 * devolviendo los metadatos HTTP (`status`, `correlationId`) junto con el DTO inmutable.
 */
export async function fetchInitialPackStatusWithMeta(
  options?: InitialPackRequestOptions
): Promise<ApiResponse<InitialPackStatusDTO>> {
  ensureAuthHttpBridgeConfigured();

  const response = await requestApiWithMeta<unknown>(INITIAL_PACK_STATUS_ENDPOINT, {
    method: "GET",
    requiresAuth: true,
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
    tokenProvider: options?.tokenProvider,
    onUnauthorized: options?.onUnauthorized,
  });

  return validateAndFreezeResponse(response);
}

/**
 * Consulta el estado actual del paquete inicial (`GET /api/v1/player/initial-pack`).
 *
 * Operación de solo lectura: nunca entrega cartas ni cubos ni reintenta la provisión.
 * Requiere sesión autenticada con rol `PLAYER`.
 */
export async function fetchInitialPackStatus(
  options?: InitialPackRequestOptions
): Promise<InitialPackStatusDTO> {
  const response = await fetchInitialPackStatusWithMeta(options);
  return response.data;
}

/**
 * Confirma la apertura del paquete inicial (`POST /api/v1/player/initial-pack/open`)
 * devolviendo los metadatos HTTP (`status`, `correlationId`) junto con el DTO inmutable.
 *
 * No envía ningún cuerpo ni parámetros de consulta para cumplir estrictamente con
 * `ConfirmarApertura(extra="forbid")` en FastAPI.
 */
export async function openInitialPackWithMeta(
  options?: InitialPackRequestOptions
): Promise<ApiResponse<InitialPackStatusDTO>> {
  ensureAuthHttpBridgeConfigured();

  const response = await requestApiWithMeta<unknown>(INITIAL_PACK_OPEN_ENDPOINT, {
    method: "POST",
    requiresAuth: true,
    body: undefined,
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
    tokenProvider: options?.tokenProvider,
    onUnauthorized: options?.onUnauthorized,
  });

  return validateAndFreezeResponse(response);
}

/**
 * Confirma la apertura del paquete inicial (`POST /api/v1/player/initial-pack/open`).
 *
 * El backend responde con `state: "COMPLETED"`, `received: true`, `opened: true`,
 * `opened_at` poblado y `cards: []`.
 */
export async function openInitialPack(
  options?: InitialPackRequestOptions
): Promise<InitialPackStatusDTO> {
  const response = await openInitialPackWithMeta(options);
  return response.data;
}
