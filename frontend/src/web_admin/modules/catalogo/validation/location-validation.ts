import type { EfectoParams, EnergyBonusMode, LocationEffectType } from "../types/location-admin.types";

export const LOCATION_VALIDATION_CONSTRAINTS = Object.freeze({
  NOMBRE_MAX_LENGTH: 100,
  DESCRIPCION_MAX_LENGTH: 500,
  CARD_LIMIT_MIN: 0,
  CARD_LIMIT_MAX: 5,
  ENERGIA_FIJA_MAX: 3,
  ENERGIA_POR_CARTAS_MAX: 2,
  EFECTO_CANTIDAD_MIN: -5,
  EFECTO_CANTIDAD_MAX: 5,
});

export interface LocationFieldErrors {
  nombre?: string;
  descripcion?: string;
  card_limit?: string;
  energia_valor?: string;
  efecto_cantidad?: string;
}

type FormValues = {
  nombre: string;
  descripcion: string;
  card_limit: number;
  energia_tipo: EnergyBonusMode;
  energia_valor: number;
  efecto_tipo: LocationEffectType;
  efecto_params: EfectoParams;
};

export function validateLocationFields(values: FormValues): LocationFieldErrors {
  const errors: LocationFieldErrors = {};
  const C = LOCATION_VALIDATION_CONSTRAINTS;

  if (!values.nombre.trim()) {
    errors.nombre = "El nombre es obligatorio.";
  } else if (values.nombre.length > C.NOMBRE_MAX_LENGTH) {
    errors.nombre = `El nombre no puede superar ${C.NOMBRE_MAX_LENGTH} caracteres.`;
  }

  if (values.descripcion.length > C.DESCRIPCION_MAX_LENGTH) {
    errors.descripcion = `La descripción no puede superar ${C.DESCRIPCION_MAX_LENGTH} caracteres.`;
  }

  if (
    !Number.isInteger(values.card_limit) ||
    values.card_limit < C.CARD_LIMIT_MIN ||
    values.card_limit > C.CARD_LIMIT_MAX
  ) {
    errors.card_limit = `El límite debe ser un entero entre ${C.CARD_LIMIT_MIN} y ${C.CARD_LIMIT_MAX}.`;
  }

  const maxEnergia =
    values.energia_tipo === "FIJA" ? C.ENERGIA_FIJA_MAX : C.ENERGIA_POR_CARTAS_MAX;
  if (
    !Number.isInteger(values.energia_valor) ||
    values.energia_valor < 0 ||
    values.energia_valor > maxEnergia
  ) {
    errors.energia_valor = `El valor de energía debe ser entre 0 y ${maxEnergia} en modo ${values.energia_tipo}.`;
  }

  if (
    values.efecto_tipo === "BONIFICACION_POR_TIPO" ||
    values.efecto_tipo === "MODIFICADOR_COSTO"
  ) {
    const cantidad: unknown = (values.efecto_params as unknown as Record<string, unknown>).cantidad;
    if (
      typeof cantidad !== "number" ||
      !Number.isInteger(cantidad) ||
      cantidad < C.EFECTO_CANTIDAD_MIN ||
      cantidad > C.EFECTO_CANTIDAD_MAX
    ) {
      errors.efecto_cantidad = `La cantidad debe ser un entero entre ${C.EFECTO_CANTIDAD_MIN} y ${C.EFECTO_CANTIDAD_MAX}.`;
    }
  }

  return errors;
}
