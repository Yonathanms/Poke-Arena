/**
 * Reglas puras y constantes de validación para 2.1.1 — Crear Carta.
 *
 * Esta capa centraliza las invariantes del contrato HTTP (`CARD_CREATION_FRONTEND_HANDOFF.md`)
 * y del dominio (`carta_model.py`, `imagen_carta_adapter.py`) sin acoplarse a componentes
 * React ni a APIs del DOM, permitiendo su verificación unitaria directa en Node.js.
 */

import type {
  AllowedImageMimeType,
  CardFieldErrors,
  CardRarity,
  CardType,
  CardValidationResult,
  CreateCardFormValues,
  ImageDimensions,
  ImageFileCandidate,
} from "../types/card-admin.types";

/** Códigos canónicos de tipos elementales aceptados por PostgreSQL y el dominio. */
export const CARD_TYPES: readonly CardType[] = Object.freeze([
  "FUE",
  "AGU",
  "PLA",
  "ELE",
  "PSI",
  "LUC",
]);

/** Códigos canónicos de rareza aceptados por PostgreSQL y el dominio. */
export const CARD_RARITIES: readonly CardRarity[] = Object.freeze([
  "COMUN",
  "POCO_COMUN",
  "RARA",
  "LEGENDARIA",
]);

/** Formatos MIME de imagen permitidos en el cliente y servidor. */
export const ALLOWED_IMAGE_MIME_TYPES: readonly AllowedImageMimeType[] = Object.freeze([
  "image/png",
  "image/jpeg",
  "image/webp",
]);

/** Restricciones contractuales exactas sincronizadas con el backend 1G. */
export const CARD_VALIDATION_CONSTRAINTS = Object.freeze({
  NAME_MIN_LENGTH: 1,
  NAME_MAX_LENGTH: 100,
  COST_MIN: 0,
  COST_MAX: 10,
  POWER_MIN: -20,
  POWER_MAX: 20,
  ABILITY_CODE_PATTERN: /^HAB-[0-9]{3}$/,
  IDEMPOTENCY_KEY_PATTERN: /^[!-+\x2D-~]{1,128}$/,
  IMAGE_MIN_BYTES: 1,
  IMAGE_MAX_BYTES: 5_000_000,
  IMAGE_MAX_PIXELS: 20_000_000,
  IMAGE_MIN_WIDTH: 600,
  IMAGE_MIN_HEIGHT: 840,
  IMAGE_ASPECT_WIDTH: 5,
  IMAGE_ASPECT_HEIGHT: 7,
});

const CARD_TYPE_SET: ReadonlySet<string> = new Set(CARD_TYPES);
const CARD_RARITY_SET: ReadonlySet<string> = new Set(CARD_RARITIES);
const ALLOWED_MIME_SET: ReadonlySet<string> = new Set(ALLOWED_IMAGE_MIME_TYPES);

/**
 * Recorta los espacios exteriores del nombre tal como hace `DatosCarta.normalizados()`
 * en el backend antes de validar su longitud y calcular la huella de idempotencia.
 */
export function normalizeCardName(rawName: string): string {
  return rawName.trim();
}

/**
 * Valida el nombre de la carta: entre 1 y 100 caracteres tras recortar espacios externos,
 * sin caracteres nulos (`\0`).
 */
export function validateCardName(rawName: string): string | null {
  if (typeof rawName !== "string") {
    return "El nombre de la carta es obligatorio.";
  }
  if (rawName.includes("\0")) {
    return "El nombre contiene caracteres no permitidos.";
  }
  const normalized = normalizeCardName(rawName);
  if (normalized.length < CARD_VALIDATION_CONSTRAINTS.NAME_MIN_LENGTH) {
    return "El nombre de la carta es obligatorio.";
  }
  if (normalized.length > CARD_VALIDATION_CONSTRAINTS.NAME_MAX_LENGTH) {
    return `El nombre no puede superar ${CARD_VALIDATION_CONSTRAINTS.NAME_MAX_LENGTH} caracteres.`;
  }
  return null;
}

/**
 * Valida el costo de energía: entero exacto entre 0 y 10.
 */
export function validateCardCost(cost: number): string | null {
  if (!Number.isInteger(cost)) {
    return "El costo debe ser un número entero.";
  }
  if (cost < CARD_VALIDATION_CONSTRAINTS.COST_MIN || cost > CARD_VALIDATION_CONSTRAINTS.COST_MAX) {
    return `El costo debe estar entre ${CARD_VALIDATION_CONSTRAINTS.COST_MIN} y ${CARD_VALIDATION_CONSTRAINTS.COST_MAX}.`;
  }
  return null;
}

/**
 * Valida el poder base: entero exacto entre -20 y 20.
 */
export function validateCardPower(power: number): string | null {
  if (!Number.isInteger(power)) {
    return "El poder debe ser un número entero.";
  }
  if (
    power < CARD_VALIDATION_CONSTRAINTS.POWER_MIN ||
    power > CARD_VALIDATION_CONSTRAINTS.POWER_MAX
  ) {
    return `El poder debe estar entre ${CARD_VALIDATION_CONSTRAINTS.POWER_MIN} y ${CARD_VALIDATION_CONSTRAINTS.POWER_MAX}.`;
  }
  return null;
}

/**
 * Verifica que el tipo elemental pertenezca al conjunto canónico (`FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC`).
 */
export function isValidCardType(value: string): value is CardType {
  return CARD_TYPE_SET.has(value);
}

export function validateCardType(cardType: string): string | null {
  if (!isValidCardType(cardType)) {
    return "Selecciona un tipo elemental válido (FUE, AGU, PLA, ELE, PSI, LUC).";
  }
  return null;
}

/**
 * Verifica que la rareza pertenezca al conjunto canónico (`COMUN`, `POCO_COMUN`, `RARA`, `LEGENDARIA`).
 */
export function isValidCardRarity(value: string): value is CardRarity {
  return CARD_RARITY_SET.has(value);
}

export function validateCardRarity(rarity: string): string | null {
  if (!isValidCardRarity(rarity)) {
    return "Selecciona una rareza válida (COMUN, POCO_COMUN, RARA, LEGENDARIA).";
  }
  return null;
}

/**
 * Valida el código de habilidad (`HAB-000` .. `HAB-999`) y, opcionalmente,
 * que exista dentro del listado administrativo cargado desde el backend.
 */
export function validateAbilityCode(
  abilityCode: string,
  availableCodes?: ReadonlyArray<string>
): string | null {
  const trimmed = typeof abilityCode === "string" ? abilityCode.trim() : "";
  if (!trimmed) {
    return "Debes seleccionar una habilidad.";
  }
  if (!CARD_VALIDATION_CONSTRAINTS.ABILITY_CODE_PATTERN.test(trimmed)) {
    return "El código de habilidad debe tener el formato HAB-NNN.";
  }
  if (availableCodes && availableCodes.length > 0 && !availableCodes.includes(trimmed)) {
    return "La habilidad seleccionada no existe en el catálogo actual.";
  }
  return null;
}

/**
 * Verifica que el MIME type reportado sea PNG, JPEG o WebP.
 */
export function isAllowedImageMimeType(mimeType: string): mimeType is AllowedImageMimeType {
  return ALLOWED_MIME_SET.has(mimeType.trim().toLowerCase());
}

/**
 * Valida los metadatos básicos del archivo (presencia, formato MIME y rango de 1 a 5 000 000 bytes).
 * El límite es exactamente 5 000 000 bytes (no 5 MiB = 5 242 880 bytes), idéntico a `MAX_IMAGE_BYTES`.
 */
export function validateImageFileMetadata(candidate: ImageFileCandidate | null | undefined): string | null {
  if (!candidate) {
    return "Se requiere seleccionar una imagen original para la carta.";
  }
  if (!isAllowedImageMimeType(candidate.mimeType)) {
    return "Formato no permitido. Usa una imagen PNG, JPEG o WebP.";
  }
  if (!Number.isInteger(candidate.sizeBytes) || candidate.sizeBytes < CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_BYTES) {
    return "El archivo de imagen está vacío.";
  }
  if (candidate.sizeBytes > CARD_VALIDATION_CONSTRAINTS.IMAGE_MAX_BYTES) {
    return "La imagen supera el tamaño máximo permitido de 5 000 000 bytes (5 MB).";
  }
  return null;
}

/**
 * Comprueba la proporción exacta 5:7 usando aritmética entera (`7 * width === 5 * height`),
 * evitando errores de precisión en coma flotante y coincidiendo con `imagen_carta_adapter.py`.
 */
export function hasExactCardAspectRatio(dimensions: ImageDimensions): boolean {
  if (!Number.isInteger(dimensions.width) || !Number.isInteger(dimensions.height)) {
    return false;
  }
  if (dimensions.width <= 0 || dimensions.height <= 0) {
    return false;
  }
  return (
    CARD_VALIDATION_CONSTRAINTS.IMAGE_ASPECT_HEIGHT * dimensions.width ===
    CARD_VALIDATION_CONSTRAINTS.IMAGE_ASPECT_WIDTH * dimensions.height
  );
}

/**
 * Valida las dimensiones visuales de la imagen (mínimo 600 × 840 px, proporción exacta 5:7
 * y techo de 20 000 000 píxeles del backend).
 */
export function validateImageDimensions(dimensions: ImageDimensions): string | null {
  const { width, height } = dimensions;
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    return "No se pudieron determinar las dimensiones de la imagen.";
  }
  if (width * height > CARD_VALIDATION_CONSTRAINTS.IMAGE_MAX_PIXELS) {
    return "Las dimensiones de la imagen superan el límite de 20 megapíxeles.";
  }
  if (
    width < CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_WIDTH ||
    height < CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_HEIGHT
  ) {
    return `La resolución mínima requerida es ${CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_WIDTH} × ${CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_HEIGHT} píxeles.`;
  }
  if (!hasExactCardAspectRatio(dimensions)) {
    return "La imagen debe tener una proporción vertical exacta de 5:7 (por ejemplo, 600 × 840 px).";
  }
  return null;
}

/**
 * Valida que una clave de idempotencia cumpla el patrón exigido por el backend:
 * 1 a 128 caracteres ASCII visibles (`0x21..0x7E`), excluyendo la coma (`0x2C`).
 */
export function isValidIdempotencyKey(key: string): boolean {
  return typeof key === "string" && CARD_VALIDATION_CONSTRAINTS.IDEMPOTENCY_KEY_PATTERN.test(key);
}

/** Interfaz inyectable de creación/revocación de Object URLs para pruebas deterministas. */
export interface ObjectUrlManager {
  readonly createObjectURL: (blob: Blob) => string;
  readonly revokeObjectURL: (url: string) => void;
}

/** Función inyectable que obtiene las dimensiones visuales de un archivo de imagen. */
export type ImageDimensionsDecoder = (file: Blob, objectUrl: string) => Promise<ImageDimensions>;

/** Resultado discriminado de la inspección y decodificación asíncrona de una imagen. */
export type ImageInspectionOutcome =
  | {
      readonly status: "valid";
      readonly previewUrl: string;
      readonly dimensions: ImageDimensions;
      readonly sizeBytes: number;
      readonly mimeType: AllowedImageMimeType;
    }
  | {
      readonly status: "invalid";
      readonly errorMessage: string;
    }
  | {
      readonly status: "cancelled";
    };

/**
 * Controlador secuencial para validar y previsualizar archivos de imagen evitando
 * fugas de `URL.createObjectURL` y condiciones de carrera cuando el usuario selecciona
 * o reemplaza archivos rápidamente.
 *
 * Garantías:
 * 1. Cada nueva selección o limpieza incrementa el contador de generación e invalida
 *    cualquier decodificación anterior aún en vuelo.
 * 2. Si una decodificación antigua termina después de haber sido reemplazada o limpiada,
 *    su `objectUrl` temporal se revoca inmediatamente y su resultado se descarta (`cancelled`).
 * 3. Si la validación de metadatos o dimensiones falla, la `objectUrl` recién creada se
 *    revoca antes de retornar `invalid`.
 * 4. Cuando una nueva imagen resulta válida, se revoca la `objectUrl` de la imagen válida
 *    anterior antes de conservar la nueva.
 */
export class SequentialImageSelectionPipeline {
  private readonly urlManager: ObjectUrlManager;
  private readonly decodeDimensions: ImageDimensionsDecoder;
  private currentGeneration = 0;
  private activePreviewUrl: string | null = null;

  constructor(options: {
    readonly urlManager: ObjectUrlManager;
    readonly decodeDimensions: ImageDimensionsDecoder;
  }) {
    this.urlManager = options.urlManager;
    this.decodeDimensions = options.decodeDimensions;
  }

  public getCurrentPreviewUrl(): string | null {
    return this.activePreviewUrl;
  }

  /**
   * Revoca la URL de previsualización activa (si existe) e invalida cualquier
   * operación de decodificación en curso.
   */
  public clearActiveSelection(): void {
    this.currentGeneration += 1;
    this.revokeActivePreview();
  }

  private revokeActivePreview(): void {
    if (this.activePreviewUrl !== null) {
      const urlToRevoke = this.activePreviewUrl;
      this.activePreviewUrl = null;
      this.urlManager.revokeObjectURL(urlToRevoke);
    }
  }

  /**
   * Valida metadatos, crea un `objectUrl`, decodifica dimensiones y verifica
   * proporción 5:7, mínimo 600×840 y techo de 20 MP.
   */
  public async inspectFile(file: Blob & { readonly name?: string }): Promise<ImageInspectionOutcome> {
    const generation = ++this.currentGeneration;

    // Al iniciar una nueva selección, revocamos cualquier preview previa activa
    this.revokeActivePreview();

    const metadataError = validateImageFileMetadata({
      sizeBytes: file.size,
      mimeType: file.type,
      fileName: file.name,
    });
    if (metadataError !== null) {
      return { status: "invalid", errorMessage: metadataError };
    }

    const normalizedMime = file.type.trim().toLowerCase() as AllowedImageMimeType;
    const candidateUrl = this.urlManager.createObjectURL(file);

    let dimensions: ImageDimensions;
    try {
      dimensions = await this.decodeDimensions(file, candidateUrl);
    } catch {
      this.urlManager.revokeObjectURL(candidateUrl);
      if (generation !== this.currentGeneration) {
        return { status: "cancelled" };
      }
      return {
        status: "invalid",
        errorMessage: "No se pudo decodificar la imagen. Verifica que el archivo PNG, JPEG o WebP no esté dañado.",
      };
    }

    // Si mientras se decodificaba el usuario eligió otro archivo o desmontó el componente:
    if (generation !== this.currentGeneration) {
      this.urlManager.revokeObjectURL(candidateUrl);
      return { status: "cancelled" };
    }

    const dimensionError = validateImageDimensions(dimensions);
    if (dimensionError !== null) {
      this.urlManager.revokeObjectURL(candidateUrl);
      return { status: "invalid", errorMessage: dimensionError };
    }

    this.activePreviewUrl = candidateUrl;
    return {
      status: "valid",
      previewUrl: candidateUrl,
      dimensions,
      sizeBytes: file.size,
      mimeType: normalizedMime,
    };
  }
}

/**
 * Ejecuta la validación integral de los campos de Crear Carta y devuelve los valores
 * normalizados si todos los campos son válidos.
 */
export function validateCreateCardForm(
  values: CreateCardFormValues,
  options?: {
    readonly availableAbilityCodes?: ReadonlyArray<string>;
    readonly imageCandidate?: ImageFileCandidate | null;
    readonly imageDimensions?: ImageDimensions | null;
  }
): CardValidationResult {
  const errors: CardFieldErrors = {};

  const nameError = validateCardName(values.name);
  if (nameError) errors.name = nameError;

  const costError = validateCardCost(values.cost);
  if (costError) errors.cost = costError;

  const powerError = validateCardPower(values.power);
  if (powerError) errors.power = powerError;

  const typeError = validateCardType(values.card_type);
  if (typeError) errors.card_type = typeError;

  const rarityError = validateCardRarity(values.rarity);
  if (rarityError) errors.rarity = rarityError;

  const abilityError = validateAbilityCode(values.ability_code, options?.availableAbilityCodes);
  if (abilityError) errors.ability_code = abilityError;

  if (options && "imageCandidate" in options) {
    const fileError = validateImageFileMetadata(options.imageCandidate);
    if (fileError) {
      errors.image = fileError;
    } else if (options.imageDimensions) {
      const dimError = validateImageDimensions(options.imageDimensions);
      if (dimError) errors.image = dimError;
    }
  }

  const valid = Object.keys(errors).length === 0;
  if (!valid) {
    return { valid: false, errors };
  }

  return {
    valid: true,
    errors: {},
    normalizedValues: {
      name: normalizeCardName(values.name),
      cost: values.cost,
      power: values.power,
      card_type: values.card_type,
      rarity: values.rarity,
      ability_code: values.ability_code.trim(),
    },
  };
}
