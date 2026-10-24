export type CardType = "FUE" | "AGU" | "PLA" | "ELE" | "PSI" | "LUC";

export type CardRarity = "COMUN" | "POCO_COMUN" | "RARA" | "LEGENDARIA";

export type CardImageStatus =
  | "PENDING"
  | "PROCESSING"
  | "RETRY_PENDING"
  | "READY"
  | "FAILED";

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

export interface AbilitySummaryDTO {
  code: string;
  name: string;
  trigger: string | null;
  effect: string | null;
  affected_card_type: CardType | null;
  parameters: Record<string, unknown>;
}

export interface CardCreatedResponseDTO {
  id: string;
  code: string;
  name: string;
  cost: number;
  power: number;
  card_type: CardType;
  rarity: CardRarity;
  ability: AbilitySummaryDTO;
  image_status: CardImageStatus | null;
  image_url: string | null;
  thumbnail_url: string | null;
  available_to_players: false;
  status_url: string;
}

export interface CardImageStatusResponseDTO extends Omit<CardCreatedResponseDTO, "image_status" | "available_to_players"> {
  image_status: CardImageStatus;
  available_to_players: boolean;
  attempts: number;
  last_error: string | null;
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
  image_url: string | null;
  thumbnail_url?: string | null;
  ability?: AbilityDTO | AbilitySummaryDTO | null;
  image_status?: CardImageStatus | null;
  available_to_players?: boolean;
  status_url?: string;
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
