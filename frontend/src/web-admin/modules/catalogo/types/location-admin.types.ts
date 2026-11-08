// Tipos para el módulo de gestión de ubicaciones del portal admin

export type EnergyBonusMode = "FIJA" | "POR_CARTAS";

export type LocationEffectType =
  | "BONIFICACION_POR_TIPO"
  | "MODIFICADOR_COSTO"
  | "RESTRICCION_TURNO";

export type PokemonType = "FUE" | "AGU" | "PLA" | "ELE" | "PSI" | "LUC";

export interface BonificacionPorTipoParams {
  tipo: PokemonType;
  cantidad: number; // -5..+5
}

export interface ModificadorCostoParams {
  cantidad: number; // -5..+5
  tipo?: PokemonType;
}

export interface RestriccionTurnoParams {
  turnos: number[]; // enteros positivos
}

export type EfectoParams =
  | BonificacionPorTipoParams
  | ModificadorCostoParams
  | RestriccionTurnoParams;

export interface CreateLocationFormValues {
  nombre: string;
  descripcion: string;
  card_limit: number;
  energia_tipo: EnergyBonusMode;
  energia_valor: number;
  efecto_tipo: LocationEffectType;
  efecto_params: EfectoParams;
  imagen: File | null;
}

export interface LocationResponseDTO {
  id: string;
  nombre: string;
  descripcion: string;
  card_limit: number;
  energia_tipo: EnergyBonusMode;
  energia_valor: number;
  efecto_tipo: LocationEffectType;
  efecto_params: EfectoParams;
  url_grande: string;
  url_tablero: string;
  created_at: string | null;
}
