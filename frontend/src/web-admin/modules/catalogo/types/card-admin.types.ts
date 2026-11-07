/**
 * Contratos TypeScript para el módulo administrativo de Catálogo (2.1.1 — Crear Carta).
 *
 * Refleja los tipos exactos expuestos por el backend en la Entrega 1G
 * (`cartas_controller.py`, `cartas_dtos.py`, `carta_model.py`, `imagen_model.py`
 * y `CARD_CREATION_FRONTEND_HANDOFF.md`).
 */

/** Códigos canónicos de tipos elementales aceptados por PostgreSQL y el dominio. */
export type CardType = "FUE" | "AGU" | "PLA" | "ELE" | "PSI" | "LUC";

/** Códigos canónicos de rareza aceptados por PostgreSQL y el dominio. */
export type CardRarity = "COMUN" | "POCO_COMUN" | "RARA" | "LEGENDARIA";

/** Formatos de archivo de imagen admitidos por el procesador Pillow del backend. */
export type AllowedImageMimeType = "image/png" | "image/jpeg" | "image/webp";

/** Estado autoritativo de imagen confirmado al responder 201 en Crear Carta. */
export type CardImageStatus = "READY";

/**
 * Elemento devuelto por `GET /api/v1/content/abilities` (`HabilidadSeleccionable`).
 * La lista viene ordenada por `code` e incluye `HAB-000` ("Sin Habilidad").
 */
export interface AbilityOptionDTO {
  readonly code: string;
  readonly name: string;
}

/**
 * Campos de entrada que el administrador completa en el formulario de Crear Carta.
 */
export interface CreateCardFormValues {
  readonly name: string;
  readonly cost: number;
  readonly power: number;
  readonly card_type: CardType;
  readonly rarity: CardRarity;
  readonly ability_code: string;
}

/**
 * Solicitud completa para `POST /api/v1/content/cards` (`multipart/form-data`).
 */
export interface CreateCardMultipartInput extends CreateCardFormValues {
  readonly image: Blob;
  readonly imageFileName?: string;
}

/**
 * Respuesta HTTP 201 de `POST /api/v1/content/cards` (`CartaCreada`).
 * Tanto una creación inicial como su replay idempotente devuelven esta misma estructura.
 */
export interface CardCreatedResponseDTO {
  readonly id: string;
  readonly code: string;
  readonly operation_id: string;
  readonly image_id: string;
  readonly image_status: CardImageStatus;
}

/**
 * Metadatos básicos de un archivo de imagen inspeccionados antes de decodificar píxeles.
 */
export interface ImageFileCandidate {
  readonly sizeBytes: number;
  readonly mimeType: string;
  readonly fileName?: string;
}

/**
 * Dimensiones visuales de una imagen decodificada en el cliente.
 */
export interface ImageDimensions {
  readonly width: number;
  readonly height: number;
}

/**
 * Resultado estructurado de la validación de los campos de Crear Carta.
 */
export type CardFieldName =
  | "name"
  | "cost"
  | "power"
  | "card_type"
  | "rarity"
  | "ability_code"
  | "image";

export type CardFieldErrors = Partial<Record<CardFieldName, string>>;

export interface CardValidationResult {
  readonly valid: boolean;
  readonly normalizedValues?: CreateCardFormValues;
  readonly errors: CardFieldErrors;
}
