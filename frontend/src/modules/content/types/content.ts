export type CardType = "FUE" | "AGU" | "PLA" | "ELE" | "PSI" | "LUC" | "INC";

export type CardRarity = "COMUN" | "POCO_COMUN" | "RARA" | "EPICA" | "LEGENDARIA";

export type AbilityType = "HAB-000" | "AL_REVELARSE" | "EFECTO_CONTINUO" | "EVOLUCION";

export type LocationEffectType =
  | "BONIFICACION_PODER"
  | "MODIFICADOR_COSTO"
  | "RESTRICCION_TURNO"
  | "LIMITE_CARTAS";

export interface AbilityDTO {
  ability_type: AbilityType;
  description: string;
  params: Record<string, unknown>;
}

export interface LocationEffectDTO {
  effect_type: LocationEffectType;
  description: string;
  params: Record<string, unknown>;
}

export interface CardDTO {
  id: string;
  code: string;
  name: string;
  cost: number;
  power: number;
  card_type: CardType;
  rarity: CardRarity;
  image_url: string;
  thumbnail_url?: string | null;
  ability?: AbilityDTO | null;
}

export interface LocationDTO {
  id: string;
  name: string;
  image_url: string;
  thumbnail_url?: string | null;
  effect: LocationEffectDTO;
}

export interface SearchCardsResponseDTO {
  items: CardDTO[];
  total: number;
  skip: number;
  limit: number;
}
