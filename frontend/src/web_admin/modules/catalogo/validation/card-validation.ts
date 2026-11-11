/**
 * Reglas puras y funciones de validación para 2.1.1 — Crear Carta.
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
  ValidatedCardImageSelection,
} from "../types/card-admin.types";

/** Códigos canónicos de tipos elementales aceptados por el dominio. */
export const CARD_TYPES: readonly CardType[] = [
  "FUE",
  "AGU",
  "PLA",
  "ELE",
  "PSI",
  "LUC",
];

/** Códigos canónicos de rareza aceptados por el dominio. */
export const CARD_RARITIES: readonly CardRarity[] = [
  "COMUN",
  "POCO_COMUN",
  "RARA",
  "LEGENDARIA",
];

/** Formatos MIME de imagen permitidos (PNG, JPG/JPEG, WebP). */
export const ALLOWED_IMAGE_MIME_TYPES: readonly AllowedImageMimeType[] = [
  "image/png",
  "image/jpeg",
  "image/webp",
];

/** Restricciones de negocio de la historia de usuario 2.1.1. */
export const CARD_VALIDATION_CONSTRAINTS = {
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
} as const;

export function normalizeCardName(rawName: string): string {
  return rawName.trim();
}

export function validateCardName(rawName: string): string | null {
  if (typeof rawName !== "string" || rawName.includes("\0")) {
    return "El nombre de la carta es obligatorio.";
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

export function validateCardCost(cost: number): string | null {
  if (!Number.isInteger(cost)) {
    return "El costo debe ser un número entero.";
  }
  if (cost < CARD_VALIDATION_CONSTRAINTS.COST_MIN || cost > CARD_VALIDATION_CONSTRAINTS.COST_MAX) {
    return `El costo debe estar entre ${CARD_VALIDATION_CONSTRAINTS.COST_MIN} y ${CARD_VALIDATION_CONSTRAINTS.COST_MAX}.`;
  }
  return null;
}

export function validateCardPower(power: number): string | null {
  if (!Number.isInteger(power)) {
    return "El poder debe ser un número entero.";
  }
  if (power < CARD_VALIDATION_CONSTRAINTS.POWER_MIN || power > CARD_VALIDATION_CONSTRAINTS.POWER_MAX) {
    return `El poder debe estar entre ${CARD_VALIDATION_CONSTRAINTS.POWER_MIN} y ${CARD_VALIDATION_CONSTRAINTS.POWER_MAX}.`;
  }
  return null;
}

export function isValidCardType(value: string): value is CardType {
  return (CARD_TYPES as readonly string[]).includes(value);
}

export function validateCardType(cardType: string): string | null {
  if (!isValidCardType(cardType)) {
    return "Selecciona un tipo elemental válido (FUE, AGU, PLA, ELE, PSI, LUC).";
  }
  return null;
}

export function isValidCardRarity(value: string): value is CardRarity {
  return (CARD_RARITIES as readonly string[]).includes(value);
}

export function validateCardRarity(rarity: string): string | null {
  if (!isValidCardRarity(rarity)) {
    return "Selecciona una rareza válida (COMUN, POCO_COMUN, RARA, LEGENDARIA).";
  }
  return null;
}

export function validateAbilityCode(
  abilityCode: string,
  availableCodes?: ReadonlyArray<string>
): string | null {
  const trimmed = typeof abilityCode === "string" ? abilityCode.trim() : "";
  if (!trimmed) {
    return "Debes seleccionar una habilidad (al menos HAB-000 Sin Habilidad).";
  }
  if (!CARD_VALIDATION_CONSTRAINTS.ABILITY_CODE_PATTERN.test(trimmed)) {
    return "El código de habilidad debe tener el formato HAB-NNN.";
  }
  if (availableCodes && availableCodes.length > 0 && !availableCodes.includes(trimmed)) {
    return "La habilidad seleccionada no existe en el catálogo actual.";
  }
  return null;
}

export function isAllowedImageMimeType(mimeType: string): mimeType is AllowedImageMimeType {
  return (ALLOWED_IMAGE_MIME_TYPES as readonly string[]).includes(mimeType.trim().toLowerCase());
}

export function validateImageFileMetadata(
  candidate: ImageFileCandidate | null | undefined
): string | null {
  if (!candidate) {
    return "Se requiere seleccionar una imagen para la carta.";
  }
  if (!isAllowedImageMimeType(candidate.mimeType)) {
    return "Formato no permitido. Usa una imagen PNG, JPG o WebP.";
  }
  if (!Number.isInteger(candidate.sizeBytes) || candidate.sizeBytes < CARD_VALIDATION_CONSTRAINTS.IMAGE_MIN_BYTES) {
    return "El archivo de imagen está vacío.";
  }
  if (candidate.sizeBytes > CARD_VALIDATION_CONSTRAINTS.IMAGE_MAX_BYTES) {
    return "La imagen supera el tamaño máximo permitido de 5 MB (5 000 000 bytes).";
  }
  return null;
}

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

export function isValidIdempotencyKey(key: string): boolean {
  return typeof key === "string" && CARD_VALIDATION_CONSTRAINTS.IDEMPOTENCY_KEY_PATTERN.test(key);
}

/**
 * Carga una imagen en el navegador para obtener su ancho y alto reales.
 */
function readImageDimensions(objectUrl: string): Promise<ImageDimensions> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => reject(new Error("No se pudo leer la imagen."));
    img.src = objectUrl;
  });
}

/**
 * Valida un archivo de imagen (formato, tamaño <= 5 MB, resolución >= 600x840 y relación 5:7)
 * y genera su URL de previsualización. Si falla, revoca la URL temporal inmediatamente.
 */
export async function validateAndInspectCardImage(
  file: File
): Promise<
  | { readonly valid: true; readonly selection: ValidatedCardImageSelection }
  | { readonly valid: false; readonly error: string }
> {
  const metadataError = validateImageFileMetadata({
    sizeBytes: file.size,
    mimeType: file.type,
    fileName: file.name,
  });
  if (metadataError) {
    return { valid: false, error: metadataError };
  }

  const previewUrl = URL.createObjectURL(file);
  try {
    const dimensions = await readImageDimensions(previewUrl);
    const dimError = validateImageDimensions(dimensions);
    if (dimError) {
      URL.revokeObjectURL(previewUrl);
      return { valid: false, error: dimError };
    }

    return {
      valid: true,
      selection: {
        file,
        previewUrl,
        dimensions,
        sizeBytes: file.size,
        mimeType: file.type.trim().toLowerCase() as AllowedImageMimeType,
      },
    };
  } catch {
    URL.revokeObjectURL(previewUrl);
    return {
      valid: false,
      error: "No se pudo decodificar la imagen. Verifica que el archivo PNG, JPG o WebP sea válido.",
    };
  }
}

/**
 * Valida todos los campos del formulario de Crear Carta.
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

  if (Object.keys(errors).length > 0) {
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
