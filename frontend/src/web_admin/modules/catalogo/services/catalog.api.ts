/**
 * Servicio HTTP de Catálogo para el portal administrativo (`web_admin`).
 *
 * Responsabilidades:
 * 1. Consultar la lista autoritativa de habilidades (`GET /api/v1/content/abilities`)
 *    reutilizando el cliente HTTP de F1 y la sesión Bearer de F1/F2.
 * 2. Construir el `FormData` exacto de Crear Carta (`POST /api/v1/content/cards`) y
 *    transmitirlo junto con la cabecera `Idempotency-Key` proporcionada por el llamador.
 * 3. Validar la estructura de las respuestas (`200 OK` de habilidades y `201 Created`
 *    de creación/replay) conforme al contrato real de la Entrega 1G.
 *
 * Decisiones arquitectónicas:
 * - Este módulo NO genera, rota ni reinicia claves de idempotencia; recibe `idempotencyKey`
 *   explícitamente desde la capa de orquestación (`useCreateCard` en F4).
 * - Tampoco realiza reintentos automáticos en `POST /content/cards`; ante un error lanza
 *   el `ApiHttpError` enriquecido para que el llamador decida si conserva la clave.
 */

import {
  ApiHttpError,
  requestApiWithMeta,
  type ApiResponse,
} from "../../../../shared/services/http-client";
import { ensureAuthHttpBridgeConfigured } from "../../auth/services/auth.api";
import type {
  AbilityOptionDTO,
  CardCreatedResponseDTO,
  CardRarityOptionDTO,
  CardTypeOptionDTO,
  CreateCardMultipartInput,
} from "../types/card-admin.types";
import type { LocationResponseDTO } from "../types/location-admin.types";
import {
  CARD_VALIDATION_CONSTRAINTS,
  isValidIdempotencyKey,
  normalizeCardName,
} from "../validation/card-validation";

const ABILITIES_ENDPOINT = "/content/abilities";
const TYPES_ENDPOINT = "/content/types";
const RARITIES_ENDPOINT = "/content/rarities";
const CARDS_ENDPOINT = "/content/cards";

/** Opciones de transporte inyectables para pruebas unitarias y cancelación. */
export interface CatalogServiceRequestOptions {
  readonly fetchImpl?: typeof fetch;
  readonly signal?: AbortSignal;
}

function isAbilityOptionDTO(item: unknown): item is AbilityOptionDTO {
  if (typeof item !== "object" || item === null) {
    return false;
  }
  const candidate = item as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    CARD_VALIDATION_CONSTRAINTS.ABILITY_CODE_PATTERN.test(candidate.code) &&
    typeof candidate.name === "string" &&
    candidate.name.trim().length > 0
  );
}

function isCardCreatedResponseDTO(payload: unknown): payload is CardCreatedResponseDTO {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }
  const candidate = payload as Record<string, unknown>;
  return (
    typeof candidate.id === "string" &&
    candidate.id.trim().length > 0 &&
    typeof candidate.code === "string" &&
    /^PKA-(FUE|AGU|PLA|ELE|PSI|LUC)-[0-9]{3}$/.test(candidate.code) &&
    typeof candidate.operation_id === "string" &&
    candidate.operation_id.trim().length > 0 &&
    typeof candidate.image_id === "string" &&
    candidate.image_id.trim().length > 0 &&
    candidate.image_status === "READY"
  );
}

/**
 * Construye el cuerpo `FormData` con los 7 campos exactos exigidos por
 * `POST /api/v1/content/cards` (`name`, `cost`, `power`, `card_type`, `rarity`,
 * `ability_code`, `image`), sin campos repetidos ni adicionales.
 */
export function buildCreateCardFormData(input: CreateCardMultipartInput): FormData {
  const formData = new FormData();
  formData.set("name", normalizeCardName(input.name));
  formData.set("cost", String(input.cost));
  formData.set("power", String(input.power));
  formData.set("card_type", input.card_type);
  formData.set("rarity", input.rarity);
  formData.set("ability_code", input.ability_code.trim());

  const fileName =
    input.imageFileName ??
    (typeof File !== "undefined" && input.image instanceof File && input.image.name
      ? input.image.name
      : "card-image");

  formData.set("image", input.image, fileName);
  return formData;
}

/**
 * Obtiene la lista de habilidades seleccionables desde `GET /api/v1/content/abilities`.
 * Requiere una sesión activa con rol `PLATFORM_ADMIN`.
 */
export async function fetchSelectableAbilities(
  options?: CatalogServiceRequestOptions
): Promise<readonly AbilityOptionDTO[]> {
  ensureAuthHttpBridgeConfigured();

  const response = await requestApiWithMeta<unknown>(ABILITIES_ENDPOINT, {
    method: "GET",
    requiresAuth: true,
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
  });

  if (!Array.isArray(response.data) || !response.data.every(isAbilityOptionDTO)) {
    throw new ApiHttpError({
      status: 502,
      code: "respuesta_habilidades_invalida",
      detail: "El servidor devolvió un formato de habilidades inesperado.",
      title: "Bad Gateway",
      correlationId: response.correlationId,
    });
  }

  return Object.freeze(
    response.data.map((item) =>
      Object.freeze({
        code: item.code,
        name: item.name,
      })
    )
  );
}

/**
 * Consulta la lista oficial de tipos elementales de cartas (`GET /api/v1/content/types`).
 */
export async function fetchCardTypes(
  options?: CatalogServiceRequestOptions
): Promise<readonly CardTypeOptionDTO[]> {
  ensureAuthHttpBridgeConfigured();

  const response = await requestApiWithMeta<unknown>(TYPES_ENDPOINT, {
    method: "GET",
    requiresAuth: true,
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
  });

  if (!Array.isArray(response.data)) {
    return Object.freeze([]);
  }

  return Object.freeze(
    response.data.map((item: any) =>
      Object.freeze({
        code: String(item.code ?? ""),
        name: String(item.name ?? ""),
        description: item.description ? String(item.description) : null,
      })
    )
  );
}

/**
 * Consulta la lista oficial de rarezas de cartas (`GET /api/v1/content/rarities`).
 */
export async function fetchCardRarities(
  options?: CatalogServiceRequestOptions
): Promise<readonly CardRarityOptionDTO[]> {
  ensureAuthHttpBridgeConfigured();

  const response = await requestApiWithMeta<unknown>(RARITIES_ENDPOINT, {
    method: "GET",
    requiresAuth: true,
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
  });

  if (!Array.isArray(response.data)) {
    return Object.freeze([]);
  }

  return Object.freeze(
    response.data.map((item: any) =>
      Object.freeze({
        code: String(item.code ?? ""),
        name: String(item.name ?? ""),
      })
    )
  );
}

/**
 * Envía una solicitud de creación de carta (`POST /api/v1/content/cards`) usando
 * `multipart/form-data` y la `Idempotency-Key` suministrada por el llamador.
 *
 * No genera ni rota la clave de idempotencia ni establece `Content-Type` manual.
 */
export async function submitCreateCardMultipart(
  input: CreateCardMultipartInput,
  idempotencyKey: string,
  options?: CatalogServiceRequestOptions
): Promise<ApiResponse<CardCreatedResponseDTO>> {
  ensureAuthHttpBridgeConfigured();

  if (!isValidIdempotencyKey(idempotencyKey)) {
    throw new ApiHttpError({
      status: 422,
      code: "idempotencia_invalida",
      detail:
        "Se requiere una clave de idempotencia válida (1 a 128 caracteres ASCII visibles sin comas).",
      title: "Unprocessable Entity",
    });
  }

  const formData = buildCreateCardFormData(input);
  const response = await requestApiWithMeta<unknown>(CARDS_ENDPOINT, {
    method: "POST",
    requiresAuth: true,
    idempotencyKey,
    body: formData,
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
  });

  if (!isCardCreatedResponseDTO(response.data)) {
    throw new ApiHttpError({
      status: 502,
      code: "respuesta_carta_invalida",
      detail: "El servidor devolvió una respuesta de creación con formato inválido.",
      title: "Bad Gateway",
      correlationId: response.correlationId,
    });
  }

  return {
    status: response.status,
    data: Object.freeze({ ...response.data }),
    correlationId: response.correlationId,
  };
}

const LOCATIONS_ENDPOINT = "/content/locations";

/**
 * Envía una solicitud de creación de ubicación (`POST /api/v1/content/locations`) usando
 * `multipart/form-data`, el Bearer de la sesión administrativa activa e `Idempotency-Key`.
 */
export async function createLocation(
  formData: FormData,
  idempotencyKey: string,
  options?: CatalogServiceRequestOptions
): Promise<LocationResponseDTO> {
  ensureAuthHttpBridgeConfigured();

  if (!isValidIdempotencyKey(idempotencyKey)) {
    throw new ApiHttpError({
      status: 422,
      code: "idempotencia_invalida",
      detail:
        "Se requiere una clave de idempotencia válida (1 a 128 caracteres ASCII visibles sin comas).",
      title: "Unprocessable Entity",
    });
  }

  const response = await requestApiWithMeta<LocationResponseDTO>(LOCATIONS_ENDPOINT, {
    method: "POST",
    requiresAuth: true,
    idempotencyKey,
    body: formData,
    fetchImpl: options?.fetchImpl,
    signal: options?.signal,
  });

  return response.data;
}

