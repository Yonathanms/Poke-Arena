/**
 * Hook React y controlador determinista de estado e idempotencia para
 * 2.1.1 — Crear Carta (`useCreateCard.ts`).
 *
 * Responsabilidades:
 * 1. Coordinar el estado del formulario Crear Carta (`name`, `cost`, `power`,
 *    `card_type`, `rarity`, `ability_code`, `image`) sin recortar silenciosamente
 *    valores numéricos fuera de rango.
 * 2. Ejecutar validaciones locales exhaustivas mediante `card-validation.ts` antes
 *    de generar cualquier `Idempotency-Key` o abrir una solicitud HTTP.
 * 3. Generar `Idempotency-Key` (`crypto.randomUUID()`) una sola vez por operación
 *    lógica de creación y congelar un snapshot inmutable (`FrozenCreateCardOperation`)
 *    del payload y del archivo `File`.
 * 4. Impedir el doble envío concurrente mediante bloqueo síncrono en memoria.
 * 5. Conservar intactos el snapshot y la `Idempotency-Key` ante resultados inciertos
 *    (fallo de red, `500`, `503` incluido `commit_incierto`, `409 en_curso` o `401`),
 *    habilitando el replay explícito con los mismos datos y la misma clave.
 * 6. Limpiar la clave cuando ocurre un error definitivo (`422`, `413`, `415`, `403`,
 *    `404`, `409 conflicto_idempotencia`) para que, tras corregir el formulario, el
 *    siguiente envío genere una clave nueva.
 * 7. Preservar el borrador y cualquier operación pendiente si la sesión expira o
 *    recibe `401`, y limpiar todo rastro en memoria ante `manual_logout` o cambio
 *    de identidad de administrador.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiHttpError } from "../../../../shared/services/http-client";
import {
  getActiveSessionSnapshot,
  subscribeToSessionChanges,
} from "../../auth/services/session-store";
import type {
  ActiveSessionSnapshot,
  SessionChangeEvent,
} from "../../auth/types/auth.types";
import {
  submitCreateCardMultipart,
  type CatalogServiceRequestOptions,
} from "../services/catalog.api";
import type {
  AbilityOptionDTO,
  CardCreatedResponseDTO,
  CardFieldErrors,
  CardFieldName,
  CardRarity,
  CardType,
  CreateCardFormValues,
  CreateCardMultipartInput,
  ValidatedCardImageSelection,
} from "../types/card-admin.types";
import {
  isValidIdempotencyKey,
  normalizeCardName,
  validateAbilityCode,
  validateCardCost,
  validateCardName,
  validateCardPower,
  validateCardRarity,
  validateCardType,
  validateCreateCardForm,
} from "../validation/card-validation";

/** Estados explícitos de la máquina de creación de cartas (§7.2). */
export type CreateCardStatus =
  | "draft"
  | "validating"
  | "submitting"
  | "uncertain_outcome"
  | "success"
  | "definite_error";

/**
 * Snapshot inmutable del payload multipart y de la `Idempotency-Key`
 * congelados al iniciar un envío válido. Garantiza que cualquier reintento
 * tras un resultado incierto envíe exactamente los mismos bytes y metadatos.
 */
export interface FrozenCreateCardOperation {
  readonly input: CreateCardMultipartInput;
  readonly idempotencyKey: string;
  readonly createdAtMs: number;
}

/** Información estructurada de error para presentar en el banner principal. */
export interface CreateCardErrorInfo {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly userGuidance: string;
  readonly correlationId: string | null;
  readonly retryAfterSeconds: number | null;
  readonly isNetworkError: boolean;
  readonly isUncertainOutcome: boolean;
  readonly isSessionExpired: boolean;
}

/**
 * Registro en memoria de una carta confirmada con `201 Created` durante la
 * sesión administrativa actual (para `CatalogListScreen`).
 */
export interface CreatedCardSessionEntry {
  readonly card: CardCreatedResponseDTO;
  readonly values: CreateCardFormValues;
  readonly abilityName: string | null;
  readonly imageFileName: string;
  readonly createdAtIso: string;
  readonly correlationId: string | null;
}

/** Estado completo inmutable expuesto por `CreateCardController` y `useCreateCard`. */
export interface CreateCardState {
  readonly status: CreateCardStatus;
  readonly values: CreateCardFormValues;
  readonly rawCostInput: string;
  readonly rawPowerInput: string;
  readonly imageSelection: ValidatedCardImageSelection | null;
  readonly imageValidationError: string | null;
  readonly fieldErrors: CardFieldErrors;
  readonly activeIdempotencyKey: string | null;
  readonly frozenOperation: FrozenCreateCardOperation | null;
  readonly createdCard: CardCreatedResponseDTO | null;
  readonly lastCorrelationId: string | null;
  readonly errorInfo: CreateCardErrorInfo | null;
  readonly sessionHistory: readonly CreatedCardSessionEntry[];
}

/** Opciones de configuración e inyección para pruebas deterministas. */
export interface CreateCardControllerOptions {
  readonly fetchImpl?: typeof fetch;
  readonly generateIdempotencyKey?: () => string;
  readonly getSession?: () => ActiveSessionSnapshot | null;
  readonly subscribeSession?: (listener: (event: SessionChangeEvent) => void) => () => void;
  readonly now?: () => number;
}

const DEFAULT_FORM_VALUES: CreateCardFormValues = Object.freeze({
  name: "",
  cost: 0,
  power: 0,
  card_type: "FUE",
  rarity: "COMUN",
  ability_code: "HAB-000",
});

function createInitialState(defaultAbilityCode = "HAB-000"): CreateCardState {
  return Object.freeze({
    status: "draft",
    values: Object.freeze({
      ...DEFAULT_FORM_VALUES,
      ability_code: defaultAbilityCode,
    }),
    rawCostInput: String(DEFAULT_FORM_VALUES.cost),
    rawPowerInput: String(DEFAULT_FORM_VALUES.power),
    imageSelection: null,
    imageValidationError: null,
    fieldErrors: Object.freeze({}),
    activeIdempotencyKey: null,
    frozenOperation: null,
    createdCard: null,
    lastCorrelationId: null,
    errorInfo: null,
    sessionHistory: Object.freeze([]),
  });
}

function defaultIdempotencyKeyGenerator(): string {
  if (typeof globalThis.crypto !== "undefined" && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Fallback determinista de formato UUID v4 en entornos sin crypto.randomUUID
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

/**
 * Interpreta una cadena numérica sin recortar silenciosamente valores fuera de rango.
 * Devuelve `Number.NaN` si la cadena está vacía o no representa un número finito.
 */
export function parseUnclampedNumericInput(raw: string): number {
  const trimmed = raw.trim();
  if (trimmed.length === 0 || trimmed === "-" || trimmed === "+") {
    return Number.NaN;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

/**
 * Clasifica un error de creación de carta según el contrato RFC 7807 de la Entrega 1G
 * y determina si el resultado es incierto (debiendo conservar la `Idempotency-Key`).
 */
export function mapCreateCardError(error: unknown): CreateCardErrorInfo {
  if (error instanceof ApiHttpError) {
    const isSessionExpired = error.status === 401;
    const isUncertainOutcome = error.shouldPreserveIdempotencyKey;

    if (error.isNetworkError) {
      return Object.freeze({
        status: 0,
        code: error.code,
        title: "Fallo de comunicación — Resultado incierto",
        detail: error.detail,
        userGuidance:
          "No se recibió confirmación del servidor. Conservamos los datos exactos y la clave de idempotencia para que puedas reintentar sin duplicar la carta.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: true,
        isUncertainOutcome: true,
        isSessionExpired: false,
      });
    }

    if (isSessionExpired) {
      return Object.freeze({
        status: 401,
        code: error.code,
        title: "Sesión administrativa expirada o no válida (401)",
        detail: error.detail,
        userGuidance:
          "Inicia sesión nuevamente. Tu borrador y la clave de idempotencia en curso se mantienen protegidos en memoria para reanudar sin pérdida de datos.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: true,
        isSessionExpired: true,
      });
    }

    if (error.status === 403) {
      return Object.freeze({
        status: 403,
        code: error.code,
        title: "Acceso denegado (403)",
        detail: error.detail,
        userGuidance:
          "Esta operación requiere una sesión activa con rol PLATFORM_ADMIN.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: false,
        isSessionExpired: false,
      });
    }

    if (error.status === 409 && error.code === "en_curso") {
      return Object.freeze({
        status: 409,
        code: error.code,
        title: "Operación en curso en el servidor (409)",
        detail: error.detail,
        userGuidance:
          "El servidor continúa procesando el intento anterior con esta misma clave. Pulsa 'Reintentar operación pendiente' para consultar o completar el resultado sin crear duplicados.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: true,
        isSessionExpired: false,
      });
    }

    if (error.status === 409 && error.code === "conflicto_idempotencia") {
      return Object.freeze({
        status: 409,
        code: error.code,
        title: "Conflicto de idempotencia (409)",
        detail: error.detail,
        userGuidance:
          "La clave de idempotencia ya fue asociada a un payload distinto. Se ha liberado la clave anterior; revisa el formulario antes de enviar un nuevo intento.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: false,
        isSessionExpired: false,
      });
    }

    if (error.status === 413) {
      return Object.freeze({
        status: 413,
        code: error.code,
        title: "Archivo de imagen demasiado grande (413)",
        detail: error.detail,
        userGuidance:
          "El archivo supera el límite máximo de 5 000 000 bytes (5 MB). Reemplaza la imagen por una dentro del límite permitido.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: false,
        isSessionExpired: false,
      });
    }

    if (error.status === 415) {
      return Object.freeze({
        status: 415,
        code: error.code,
        title: "Tipo de contenido no soportado (415)",
        detail: error.detail,
        userGuidance:
          "Verifica que la imagen sea un archivo PNG, JPEG o WebP válido.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: false,
        isSessionExpired: false,
      });
    }

    if (error.status === 422) {
      return Object.freeze({
        status: 422,
        code: error.code,
        title: "Error de validación en el servidor (422)",
        detail: error.detail,
        userGuidance:
          "Corrige los campos señalados en el formulario. Al volver a enviar se generará una nueva clave de idempotencia.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: false,
        isSessionExpired: false,
      });
    }

    if (error.status === 503) {
      if (error.code === "almacenamiento") {
        return Object.freeze({
          status: 503,
          code: "almacenamiento",
          title: "Almacenamiento no disponible (503)",
          detail: error.detail || "El almacenamiento no está disponible.",
          userGuidance:
            "El servicio de almacenamiento de imágenes no está disponible. Tu borrador y la clave de idempotencia se conservan intactos; pulsa 'Reintentar operación pendiente' cuando el servicio se restablezca.",
          correlationId: error.correlationId,
          retryAfterSeconds: error.retryAfterSeconds,
          isNetworkError: false,
          isUncertainOutcome: true,
          isSessionExpired: false,
        });
      }

      if (error.code === "commit_incierto") {
        return Object.freeze({
          status: 503,
          code: "commit_incierto",
          title: "Confirmación incierta en el servidor (503)",
          detail: error.detail || "Resultado incierto. Repite con la misma clave.",
          userGuidance:
            "El servidor no pudo confirmar si la transacción finalizó. Usa 'Reintentar operación pendiente' para repetir la solicitud con la misma Idempotency-Key y recuperar la carta sin duplicarla.",
          correlationId: error.correlationId,
          retryAfterSeconds: error.retryAfterSeconds,
          isNetworkError: false,
          isUncertainOutcome: true,
          isSessionExpired: false,
        });
      }

      if (error.code === "transaccion") {
        return Object.freeze({
          status: 503,
          code: "transaccion",
          title: "Fallo de confirmación de transacción (503)",
          detail: error.detail || "No se pudo confirmar la operación.",
          userGuidance:
            "No se pudo confirmar la transacción en la base de datos. Tu borrador y la clave de idempotencia se conservan intactos; pulsa 'Reintentar operación pendiente' para repetir la solicitud.",
          correlationId: error.correlationId,
          retryAfterSeconds: error.retryAfterSeconds,
          isNetworkError: false,
          isUncertainOutcome: true,
          isSessionExpired: false,
        });
      }

      return Object.freeze({
        status: 503,
        code: error.code,
        title: "Servicio no disponible (503)",
        detail: error.detail || "El servicio no está disponible temporalmente.",
        userGuidance:
          "El servidor no está disponible temporalmente. Tu borrador y la clave de idempotencia se conservan intactos; pulsa 'Reintentar operación pendiente' para intentar nuevamente.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: true,
        isSessionExpired: false,
      });
    }

    if (error.status === 500) {
      return Object.freeze({
        status: 500,
        code: error.code,
        title: "Error interno del servidor (500)",
        detail: error.detail,
        userGuidance:
          "El servidor experimentó un error interno. Conservamos los datos y la clave de idempotencia para que puedas reintentar sin duplicar la carta.",
        correlationId: error.correlationId,
        retryAfterSeconds: error.retryAfterSeconds,
        isNetworkError: false,
        isUncertainOutcome: true,
        isSessionExpired: false,
      });
    }

    return Object.freeze({
      status: error.status,
      code: error.code,
      title: `No se pudo crear la carta (HTTP ${error.status})`,
      detail: error.detail,
      userGuidance:
        "Revisa el detalle reportado por el servidor y el identificador de correlación.",
      correlationId: error.correlationId,
      retryAfterSeconds: error.retryAfterSeconds,
      isNetworkError: false,
      isUncertainOutcome,
      isSessionExpired: false,
    });
  }

  return Object.freeze({
    status: 500,
    code: "error_inesperado_cliente",
    title: "Error inesperado al procesar la solicitud",
    detail: error instanceof Error ? error.message : "Fallo desconocido.",
    userGuidance: "Verifica el estado del formulario e inténtalo nuevamente.",
    correlationId: null,
    retryAfterSeconds: null,
    isNetworkError: false,
    isUncertainOutcome: false,
    isSessionExpired: false,
  });
}

/**
 * Controlador determinista de creación de cartas e idempotencia.
 * Separa la máquina de estados pura y la gestión de `Idempotency-Key` del ciclo
 * de renderizado de React para permitir pruebas unitarias exhaustivas de los 14
 * escenarios obligatorios de idempotencia y concurrencia.
 */
export class CreateCardController {
  private readonly fetchImpl?: typeof fetch;
  private readonly generateKey: () => string;
  private readonly getSession: () => ActiveSessionSnapshot | null;
  private readonly subscribeSession: (listener: (event: SessionChangeEvent) => void) => () => void;
  private readonly now: () => number;

  private state: CreateCardState = createInitialState();
  private readonly listeners = new Set<(state: CreateCardState) => void>();
  private availableAbilities: readonly AbilityOptionDTO[] = Object.freeze([]);
  private hasLoadedAbilities = false;
  private inFlightPromise: Promise<CardCreatedResponseDTO | null> | null = null;
  private operationGeneration = 0;
  private ownerUserId: string | null = null;
  private unsubscribeSession: (() => void) | null = null;

  constructor(options?: CreateCardControllerOptions) {
    this.fetchImpl = options?.fetchImpl;
    this.generateKey = options?.generateIdempotencyKey ?? defaultIdempotencyKeyGenerator;
    this.getSession = options?.getSession ?? getActiveSessionSnapshot;
    this.subscribeSession = options?.subscribeSession ?? subscribeToSessionChanges;
    this.now = options?.now ?? (() => Date.now());

    const active = this.getSession();
    if (active && active.role === "PLATFORM_ADMIN") {
      this.ownerUserId = active.userId;
    }
  }

  public getState(): CreateCardState {
    return this.state;
  }

  public subscribe(listener: (state: CreateCardState) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private setState(updater: (prev: CreateCardState) => CreateCardState): void {
    const next = Object.freeze(updater(this.state));
    this.state = next;
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }

  /**
   * Conecta el controlador a los eventos del almacén de sesión para:
   * - Preservar el borrador y la `Idempotency-Key` en `expired` o `unauthorized_401`.
   * - Limpiar todo el estado en `manual_logout` o cuando inicia sesión un administrador distinto.
   */
  public start(): void {
    if (!this.unsubscribeSession) {
      this.unsubscribeSession = this.subscribeSession((event) => {
        this.handleSessionEvent(event);
      });
    }
  }

  /**
   * Desconecta suscripciones e invalida respuestas en vuelo al desmontar definitivamente.
   */
  public dispose(): void {
    this.operationGeneration += 1;
    this.inFlightPromise = null;
    if (this.unsubscribeSession) {
      this.unsubscribeSession();
      this.unsubscribeSession = null;
    }
  }

  private handleSessionEvent(event: SessionChangeEvent): void {
    if (event.reason === "manual_logout") {
      this.operationGeneration += 1;
      this.inFlightPromise = null;
      this.ownerUserId = null;
      this.setState(() => createInitialState(this.resolveDefaultAbilityCode()));
      return;
    }

    if (event.session && event.session.role === "PLATFORM_ADMIN") {
      if (this.ownerUserId !== null && this.ownerUserId !== event.session.userId) {
        // Si ingresa un administrador distinto al que tenía el borrador, reiniciar por aislamiento
        this.operationGeneration += 1;
        this.inFlightPromise = null;
        this.ownerUserId = event.session.userId;
        this.setState(() => createInitialState(this.resolveDefaultAbilityCode()));
        return;
      }

      this.ownerUserId = event.session.userId;
      // Si el mismo administrador se reautenticó y había un aviso de sesión expirada,
      // mantenemos intacto el borrador y cualquier operación congelada lista para reintento.
      if (this.state.errorInfo?.isSessionExpired) {
        this.setState((prev) => ({
          ...prev,
          errorInfo: prev.frozenOperation
            ? Object.freeze({
                ...prev.errorInfo!,
                title: "Sesión restablecida — Operación pendiente lista para reintentar",
                userGuidance:
                  "Tu sesión fue renovada. Puedes reintentar la operación pendiente con la misma clave de idempotencia o desbloquear el borrador.",
                isSessionExpired: false,
              })
            : null,
          status: prev.frozenOperation ? "uncertain_outcome" : "draft",
        }));
      }
    }
  }

  private resolveDefaultAbilityCode(): string {
    if (this.availableAbilities.some((item) => item.code === "HAB-000")) {
      return "HAB-000";
    }
    return this.availableAbilities[0]?.code ?? "HAB-000";
  }

  /**
   * Sincroniza la lista de habilidades cargadas desde `useAbilities` para validar
   * que el `ability_code` seleccionado pertenezca al catálogo actual.
   */
  public syncAvailableAbilities(
    abilities: readonly AbilityOptionDTO[],
    hasLoaded = true
  ): void {
    this.availableAbilities = Object.freeze([...abilities]);
    this.hasLoadedAbilities = hasLoaded;

    if (!hasLoaded || abilities.length === 0) {
      return;
    }

    const availableCodes = abilities.map((a) => a.code);
    const currentCode = this.state.values.ability_code.trim();

    if (!currentCode) {
      const fallback = this.resolveDefaultAbilityCode();
      this.setState((prev) => ({
        ...prev,
        values: Object.freeze({
          ...prev.values,
          ability_code: fallback,
        }),
      }));
      return;
    }

    if (!availableCodes.includes(currentCode)) {
      this.setState((prev) => ({
        ...prev,
        fieldErrors: Object.freeze({
          ...prev.fieldErrors,
          ability_code: "La habilidad seleccionada no existe en el catálogo actual.",
        }),
      }));
    } else if (this.state.fieldErrors.ability_code) {
      this.setState((prev) => {
        const nextErrors = { ...prev.fieldErrors };
        delete nextErrors.ability_code;
        return {
          ...prev,
          fieldErrors: Object.freeze(nextErrors),
        };
      });
    }
  }

  /**
   * Indica si los controles de edición del formulario deben permanecer bloqueados
   * para proteger la integridad de una operación en vuelo, incierta o ya completada.
   */
  public isEditingLocked(): boolean {
    return (
      this.state.status === "submitting" ||
      this.state.status === "uncertain_outcome" ||
      this.state.status === "success"
    );
  }

  private clearDefiniteErrorOnEdit(
    prev: CreateCardState,
    editedField: CardFieldName
  ): {
    readonly status: CreateCardStatus;
    readonly errorInfo: CreateCardErrorInfo | null;
    readonly fieldErrors: CardFieldErrors;
    readonly activeIdempotencyKey: string | null;
    readonly frozenOperation: FrozenCreateCardOperation | null;
  } {
    const nextFieldErrors = { ...prev.fieldErrors };
    delete nextFieldErrors[editedField];

    return {
      status: prev.status === "definite_error" ? "draft" : prev.status,
      errorInfo: prev.status === "definite_error" ? null : prev.errorInfo,
      fieldErrors: Object.freeze(nextFieldErrors),
      // Al editar en borrador o tras error definitivo no existe operación congelada ni clave activa
      activeIdempotencyKey: null,
      frozenOperation: null,
    };
  }

  public setName(name: string): void {
    if (this.isEditingLocked()) return;
    const fieldError = name.length > 0 ? validateCardName(name) : null;
    this.setState((prev) => {
      const cleaned = this.clearDefiniteErrorOnEdit(prev, "name");
      const nextErrors = { ...cleaned.fieldErrors };
      if (fieldError) {
        nextErrors.name = fieldError;
      }
      return {
        ...prev,
        ...cleaned,
        values: Object.freeze({ ...prev.values, name }),
        fieldErrors: Object.freeze(nextErrors),
      };
    });
  }

  public setCostInput(rawCostInput: string): void {
    if (this.isEditingLocked()) return;
    const parsedCost = parseUnclampedNumericInput(rawCostInput);
    const costError = validateCardCost(parsedCost);

    this.setState((prev) => {
      const cleaned = this.clearDefiniteErrorOnEdit(prev, "cost");
      const nextErrors = { ...cleaned.fieldErrors };
      if (costError) {
        nextErrors.cost = costError;
      }
      return {
        ...prev,
        ...cleaned,
        rawCostInput,
        values: Object.freeze({ ...prev.values, cost: parsedCost }),
        fieldErrors: Object.freeze(nextErrors),
      };
    });
  }

  public setPowerInput(rawPowerInput: string): void {
    if (this.isEditingLocked()) return;
    const parsedPower = parseUnclampedNumericInput(rawPowerInput);
    const powerError = validateCardPower(parsedPower);

    this.setState((prev) => {
      const cleaned = this.clearDefiniteErrorOnEdit(prev, "power");
      const nextErrors = { ...cleaned.fieldErrors };
      if (powerError) {
        nextErrors.power = powerError;
      }
      return {
        ...prev,
        ...cleaned,
        rawPowerInput,
        values: Object.freeze({ ...prev.values, power: parsedPower }),
        fieldErrors: Object.freeze(nextErrors),
      };
    });
  }

  public setCardType(cardType: CardType): void {
    if (this.isEditingLocked()) return;
    const typeError = validateCardType(cardType);

    this.setState((prev) => {
      const cleaned = this.clearDefiniteErrorOnEdit(prev, "card_type");
      const nextErrors = { ...cleaned.fieldErrors };
      if (typeError) {
        nextErrors.card_type = typeError;
      }
      return {
        ...prev,
        ...cleaned,
        values: Object.freeze({ ...prev.values, card_type: cardType }),
        fieldErrors: Object.freeze(nextErrors),
      };
    });
  }

  public setRarity(rarity: CardRarity): void {
    if (this.isEditingLocked()) return;
    const rarityError = validateCardRarity(rarity);

    this.setState((prev) => {
      const cleaned = this.clearDefiniteErrorOnEdit(prev, "rarity");
      const nextErrors = { ...cleaned.fieldErrors };
      if (rarityError) {
        nextErrors.rarity = rarityError;
      }
      return {
        ...prev,
        ...cleaned,
        values: Object.freeze({ ...prev.values, rarity }),
        fieldErrors: Object.freeze(nextErrors),
      };
    });
  }

  public setAbilityCode(abilityCode: string): void {
    if (this.isEditingLocked()) return;
    const availableCodes =
      this.availableAbilities.length > 0 ? this.availableAbilities.map((a) => a.code) : undefined;
    const abilityError = validateAbilityCode(abilityCode, availableCodes);

    this.setState((prev) => {
      const cleaned = this.clearDefiniteErrorOnEdit(prev, "ability_code");
      const nextErrors = { ...cleaned.fieldErrors };
      if (abilityError) {
        nextErrors.ability_code = abilityError;
      }
      return {
        ...prev,
        ...cleaned,
        values: Object.freeze({ ...prev.values, ability_code: abilityCode }),
        fieldErrors: Object.freeze(nextErrors),
      };
    });
  }

  public setImageSelection(selection: ValidatedCardImageSelection | null): void {
    if (this.isEditingLocked()) return;
    this.setState((prev) => {
      const cleaned = this.clearDefiniteErrorOnEdit(prev, "image");
      return {
        ...prev,
        ...cleaned,
        imageSelection: selection,
        imageValidationError: selection ? null : prev.imageValidationError,
      };
    });
  }

  public setImageValidationError(errorMessage: string | null): void {
    if (this.isEditingLocked()) return;
    this.setState((prev) => {
      const nextErrors = { ...prev.fieldErrors };
      if (errorMessage) {
        nextErrors.image = errorMessage;
      } else {
        delete nextErrors.image;
      }
      return {
        ...prev,
        imageValidationError: errorMessage,
        fieldErrors: Object.freeze(nextErrors),
      };
    });
  }

  public dismissErrorBanner(): void {
    if (this.state.status === "uncertain_outcome") {
      // En resultado incierto el banner contiene las acciones de recuperación; no se oculta silenciosamente
      return;
    }
    this.setState((prev) => ({
      ...prev,
      errorInfo: null,
      status: prev.status === "definite_error" ? "draft" : prev.status,
    }));
  }

  /**
   * Valida todos los campos del formulario y la imagen seleccionada.
   * Si algún campo falla, registra `fieldErrors` y NO genera `Idempotency-Key`.
   */
  public validateCurrentDraft(): {
    readonly valid: boolean;
    readonly normalizedValues?: CreateCardFormValues;
    readonly errors: CardFieldErrors;
  } {
    const availableCodes =
      this.availableAbilities.length > 0 ? this.availableAbilities.map((a) => a.code) : undefined;

    const imageSelection = this.state.imageSelection;
    const validation = validateCreateCardForm(this.state.values, {
      availableAbilityCodes: availableCodes,
      imageCandidate: imageSelection
        ? {
            sizeBytes: imageSelection.sizeBytes,
            mimeType: imageSelection.mimeType,
            fileName: imageSelection.file.name,
          }
        : null,
      imageDimensions: imageSelection ? imageSelection.dimensions : null,
    });

    const errors: CardFieldErrors = { ...validation.errors };

    if (this.state.imageValidationError) {
      errors.image = this.state.imageValidationError;
    }

    if (this.hasLoadedAbilities && this.availableAbilities.length === 0) {
      errors.ability_code =
        "No hay habilidades disponibles en el catálogo. Recarga las habilidades antes de crear una carta.";
    }

    const valid = Object.keys(errors).length === 0 && validation.normalizedValues !== undefined;
    return {
      valid,
      normalizedValues: valid ? validation.normalizedValues : undefined,
      errors: Object.freeze(errors),
    };
  }

  /**
   * Inicia una solicitud de creación de carta:
   * - Si ya hay una solicitud en vuelo, devuelve la misma promesa (bloqueo de doble clic).
   * - Si la carta ya fue creada (`status === "success"`), bloquea el reenvío.
   * - Si existe una operación en `uncertain_outcome`, delega en `retryPendingOperation()`
   *   para reutilizar exactamente el mismo snapshot e `Idempotency-Key`.
   * - Si está en `draft` o `definite_error`, valida localmente; solo si es válido genera
   *   una nueva `Idempotency-Key` y congela el snapshot antes de llamar al backend.
   */
  public async submit(): Promise<CardCreatedResponseDTO | null> {
    if (this.inFlightPromise !== null) {
      return this.inFlightPromise;
    }

    if (this.state.status === "success") {
      return this.state.createdCard;
    }

    if (this.state.status === "uncertain_outcome" && this.state.frozenOperation !== null) {
      return this.retryPendingOperation();
    }

    this.setState((prev) => ({
      ...prev,
      status: "validating",
      errorInfo: null,
    }));

    const validation = this.validateCurrentDraft();
    if (!validation.valid || !validation.normalizedValues || !this.state.imageSelection) {
      this.setState((prev) => ({
        ...prev,
        status: "draft",
        fieldErrors: validation.errors,
        activeIdempotencyKey: null,
        frozenOperation: null,
      }));
      return null;
    }

    const generatedKey = this.generateKey();
    if (!isValidIdempotencyKey(generatedKey)) {
      this.setState((prev) => ({
        ...prev,
        status: "definite_error",
        errorInfo: Object.freeze({
          status: 422,
          code: "idempotencia_invalida",
          title: "Clave de idempotencia inválida",
          detail: "No se pudo generar una clave de idempotencia válida.",
          userGuidance: "Intenta guardar la carta nuevamente.",
          correlationId: null,
          retryAfterSeconds: null,
          isNetworkError: false,
          isUncertainOutcome: false,
          isSessionExpired: false,
        }),
      }));
      return null;
    }

    const frozenInput: CreateCardMultipartInput = Object.freeze({
      name: normalizeCardName(validation.normalizedValues.name),
      cost: validation.normalizedValues.cost,
      power: validation.normalizedValues.power,
      card_type: validation.normalizedValues.card_type,
      rarity: validation.normalizedValues.rarity,
      ability_code: validation.normalizedValues.ability_code.trim(),
      image: this.state.imageSelection.file,
      imageFileName: this.state.imageSelection.file.name,
    });

    const frozenOperation: FrozenCreateCardOperation = Object.freeze({
      input: frozenInput,
      idempotencyKey: generatedKey,
      createdAtMs: this.now(),
    });

    return this.executeFrozenOperation(frozenOperation);
  }

  /**
   * Reintenta explícitamente una operación cuyo resultado fue incierto (`500`, `503`,
   * `409 en_curso`, fallo de red o `401` tras reautenticación) utilizando exactamente
   * el mismo snapshot `CreateCardMultipartInput` y la misma `Idempotency-Key`.
   */
  public async retryPendingOperation(): Promise<CardCreatedResponseDTO | null> {
    if (this.inFlightPromise !== null) {
      return this.inFlightPromise;
    }

    const frozen = this.state.frozenOperation;
    if (!frozen) {
      return null;
    }

    return this.executeFrozenOperation(frozen);
  }

  private async executeFrozenOperation(
    frozenOperation: FrozenCreateCardOperation
  ): Promise<CardCreatedResponseDTO | null> {
    const currentGen = ++this.operationGeneration;
    const activeSession = this.getSession();
    if (activeSession && activeSession.role === "PLATFORM_ADMIN") {
      this.ownerUserId = activeSession.userId;
    }

    this.setState((prev) => ({
      ...prev,
      status: "submitting",
      values: Object.freeze({
        name: frozenOperation.input.name,
        cost: frozenOperation.input.cost,
        power: frozenOperation.input.power,
        card_type: frozenOperation.input.card_type,
        rarity: frozenOperation.input.rarity,
        ability_code: frozenOperation.input.ability_code,
      }),
      rawCostInput: String(frozenOperation.input.cost),
      rawPowerInput: String(frozenOperation.input.power),
      fieldErrors: Object.freeze({}),
      activeIdempotencyKey: frozenOperation.idempotencyKey,
      frozenOperation,
      errorInfo: null,
    }));

    const promise = (async (): Promise<CardCreatedResponseDTO | null> => {
      try {
        const response = await submitCreateCardMultipart(
          frozenOperation.input,
          frozenOperation.idempotencyKey,
          { fetchImpl: this.fetchImpl }
        );

        if (currentGen !== this.operationGeneration) {
          return null;
        }

        const matchedAbility = this.availableAbilities.find(
          (item) => item.code === frozenOperation.input.ability_code
        );

        const newEntry: CreatedCardSessionEntry = Object.freeze({
          card: response.data,
          values: Object.freeze({
            name: frozenOperation.input.name,
            cost: frozenOperation.input.cost,
            power: frozenOperation.input.power,
            card_type: frozenOperation.input.card_type,
            rarity: frozenOperation.input.rarity,
            ability_code: frozenOperation.input.ability_code,
          }),
          abilityName: matchedAbility ? matchedAbility.name : null,
          imageFileName: frozenOperation.input.imageFileName ?? "card-image",
          createdAtIso: new Date(this.now()).toISOString(),
          correlationId: response.correlationId,
        });

        this.setState((prev) => {
          // Deduplicar por id u operation_id en caso de replay idempotente exitoso
          const alreadyRecorded = prev.sessionHistory.some(
            (entry) =>
              entry.card.id === response.data.id ||
              entry.card.operation_id === response.data.operation_id
          );
          const nextHistory = alreadyRecorded
            ? prev.sessionHistory
            : Object.freeze([newEntry, ...prev.sessionHistory]);

          return {
            ...prev,
            status: "success",
            createdCard: response.data,
            lastCorrelationId: response.correlationId,
            activeIdempotencyKey: frozenOperation.idempotencyKey,
            frozenOperation: null,
            errorInfo: null,
            sessionHistory: nextHistory,
          };
        });

        return response.data;
      } catch (error) {
        if (currentGen !== this.operationGeneration) {
          return null;
        }

        const mappedError = mapCreateCardError(error);

        if (mappedError.isUncertainOutcome) {
          // Conservar intactos el snapshot y la Idempotency-Key para replay seguro
          this.setState((prev) => ({
            ...prev,
            status: "uncertain_outcome",
            activeIdempotencyKey: frozenOperation.idempotencyKey,
            frozenOperation,
            lastCorrelationId: mappedError.correlationId,
            errorInfo: mappedError,
          }));
          return null;
        }

        // Error definitivo (422, 413, 415, 403, 404, 409 conflicto_idempotencia):
        // liberar la operación congelada y la clave para que tras corregir el formulario
        // se genere una nueva Idempotency-Key.
        this.setState((prev) => {
          const nextFieldErrors: CardFieldErrors = { ...prev.fieldErrors };
          if (mappedError.code === "imagen_invalida" || mappedError.status === 413) {
            nextFieldErrors.image = mappedError.detail;
          } else if (mappedError.code === "habilidad_inexistente") {
            nextFieldErrors.ability_code = mappedError.detail;
          }

          return {
            ...prev,
            status: "definite_error",
            activeIdempotencyKey: null,
            frozenOperation: null,
            lastCorrelationId: mappedError.correlationId,
            errorInfo: mappedError,
            fieldErrors: Object.freeze(nextFieldErrors),
          };
        });
        return null;
      } finally {
        if (currentGen === this.operationGeneration) {
          this.inFlightPromise = null;
        }
      }
    })();

    this.inFlightPromise = promise;
    return promise;
  }

  /**
   * Permite al administrador descartar explícitamente una operación en estado
   * `uncertain_outcome` para desbloquear la edición del borrador con una futura
   * clave de idempotencia nueva.
   */
  public abandonUncertainOperation(): void {
    if (this.state.status !== "uncertain_outcome") {
      return;
    }
    this.operationGeneration += 1;
    this.inFlightPromise = null;

    this.setState((prev) => ({
      ...prev,
      status: "draft",
      activeIdempotencyKey: null,
      frozenOperation: null,
      errorInfo: null,
    }));
  }

  /**
   * Reinicia el formulario tras una creación exitosa (`201 Created`) o por acción
   * explícita de limpieza en borrador, preparando una operación nueva con una
   * futura `Idempotency-Key` distinta y conservando el historial de la sesión.
   */
  public startNewCard(): void {
    if (this.state.status === "submitting") {
      return;
    }
    this.operationGeneration += 1;
    this.inFlightPromise = null;
    const defaultAbility = this.resolveDefaultAbilityCode();

    this.setState((prev) => ({
      ...createInitialState(defaultAbility),
      sessionHistory: prev.sessionHistory,
    }));
  }
}

/**
 * Instancia compartida por sesión en memoria para que el borrador y la
 * `Idempotency-Key` sobrevivan incluso si el árbol visual se oculta o
 * reestructura durante una reautenticación por `401` / expiración.
 */
let sharedSessionController: CreateCardController | null = null;

function getOrCreateSharedController(options?: CatalogServiceRequestOptions): CreateCardController {
  if (sharedSessionController === null) {
    sharedSessionController = new CreateCardController({
      fetchImpl: options?.fetchImpl,
    });
    sharedSessionController.start();
  }
  return sharedSessionController;
}

/**
 * Reinicia el controlador compartido en memoria (utilizado en `beforeEach`/`afterEach`
 * de pruebas automatizadas para garantizar aislamiento entre casos).
 */
export function resetSharedCreateCardControllerForTests(): void {
  if (sharedSessionController !== null) {
    sharedSessionController.dispose();
    sharedSessionController = null;
  }
}

export interface UseCreateCardResult extends CreateCardState {
  readonly isSubmitting: boolean;
  readonly isEditingLocked: boolean;
  readonly setName: (name: string) => void;
  readonly setCostInput: (rawCost: string) => void;
  readonly setPowerInput: (rawPower: string) => void;
  readonly setCardType: (cardType: CardType) => void;
  readonly setRarity: (rarity: CardRarity) => void;
  readonly setAbilityCode: (abilityCode: string) => void;
  readonly setImageSelection: (selection: ValidatedCardImageSelection | null) => void;
  readonly setImageValidationError: (errorMessage: string | null) => void;
  readonly syncAvailableAbilities: (
    abilities: readonly AbilityOptionDTO[],
    hasLoaded?: boolean
  ) => void;
  readonly submit: () => Promise<CardCreatedResponseDTO | null>;
  readonly retryPendingOperation: () => Promise<CardCreatedResponseDTO | null>;
  readonly abandonUncertainOperation: () => void;
  readonly startNewCard: () => void;
  readonly dismissErrorBanner: () => void;
}

/**
 * Hook React para gestionar el formulario Crear Carta, su validación y su
 * ciclo de idempotencia transaccional.
 */
export function useCreateCard(options?: {
  readonly controller?: CreateCardController;
  readonly fetchImpl?: typeof fetch;
}): UseCreateCardResult {
  const controllerRef = useRef<CreateCardController | null>(null);
  if (controllerRef.current === null) {
    controllerRef.current =
      options?.controller ?? getOrCreateSharedController({ fetchImpl: options?.fetchImpl });
  }

  const activeController = options?.controller ?? controllerRef.current;

  const [state, setState] = useState<CreateCardState>(() => activeController.getState());

  useEffect(() => {
    const ctrl = options?.controller ?? getOrCreateSharedController({ fetchImpl: options?.fetchImpl });
    controllerRef.current = ctrl;
    ctrl.start();
    setState(ctrl.getState());

    const unsubscribe = ctrl.subscribe((nextState) => {
      setState(nextState);
    });

    return () => {
      unsubscribe();
      // Si se inyectó un controlador dedicado, limpiarlo al desmontar;
      // el controlador compartido de sesión permanece vivo ante expiraciones temporales (401)
      // y se limpia automáticamente ante `manual_logout`.
      if (options?.controller) {
        ctrl.dispose();
      }
    };
  }, [options?.controller, options?.fetchImpl]);

  const setName = useCallback((name: string) => {
    controllerRef.current?.setName(name);
  }, []);

  const setCostInput = useCallback((rawCost: string) => {
    controllerRef.current?.setCostInput(rawCost);
  }, []);

  const setPowerInput = useCallback((rawPower: string) => {
    controllerRef.current?.setPowerInput(rawPower);
  }, []);

  const setCardType = useCallback((cardType: CardType) => {
    controllerRef.current?.setCardType(cardType);
  }, []);

  const setRarity = useCallback((rarity: CardRarity) => {
    controllerRef.current?.setRarity(rarity);
  }, []);

  const setAbilityCode = useCallback((abilityCode: string) => {
    controllerRef.current?.setAbilityCode(abilityCode);
  }, []);

  const setImageSelection = useCallback((selection: ValidatedCardImageSelection | null) => {
    controllerRef.current?.setImageSelection(selection);
  }, []);

  const setImageValidationError = useCallback((errorMessage: string | null) => {
    controllerRef.current?.setImageValidationError(errorMessage);
  }, []);

  const syncAvailableAbilities = useCallback(
    (abilities: readonly AbilityOptionDTO[], hasLoaded = true) => {
      controllerRef.current?.syncAvailableAbilities(abilities, hasLoaded);
    },
    []
  );

  const submit = useCallback(() => {
    if (!controllerRef.current) return Promise.resolve(null);
    return controllerRef.current.submit();
  }, []);

  const retryPendingOperation = useCallback(() => {
    if (!controllerRef.current) return Promise.resolve(null);
    return controllerRef.current.retryPendingOperation();
  }, []);

  const abandonUncertainOperation = useCallback(() => {
    controllerRef.current?.abandonUncertainOperation();
  }, []);

  const startNewCard = useCallback(() => {
    controllerRef.current?.startNewCard();
  }, []);

  const dismissErrorBanner = useCallback(() => {
    controllerRef.current?.dismissErrorBanner();
  }, []);

  return {
    ...state,
    isSubmitting: state.status === "submitting",
    isEditingLocked:
      state.status === "submitting" ||
      state.status === "uncertain_outcome" ||
      state.status === "success",
    setName,
    setCostInput,
    setPowerInput,
    setCardType,
    setRarity,
    setAbilityCode,
    setImageSelection,
    setImageValidationError,
    syncAvailableAbilities,
    submit,
    retryPendingOperation,
    abandonUncertainOperation,
    startNewCard,
    dismissErrorBanner,
  };
}
