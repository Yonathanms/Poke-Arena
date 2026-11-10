export type CardType = 'FUE' | 'AGU' | 'PLA' | 'ELE' | 'PSI' | 'LUC';
export type CardRarity = 'COMUN' | 'POCO_COMUN' | 'RARA' | 'LEGENDARIA';

export interface PokemonCard {
  id: string;
  name: string;
  code: string;
  type: CardType;
  rarity: CardRarity;
  cost: number;
  power: number;
  hp: number;
  imageUrl?: string | null;
  thumbnailUrl?: string | null;
  description?: string | null;
  price?: number | null;
  activo?: boolean;
  ability_code?: string | null;
  ability_name?: string | null;
  owned_copies: number;
  is_owned?: boolean;
}

export interface SearchCardsParams {
  q?: string | null;
  tipo?: CardType | null;
  rareza?: CardRarity | null;
  costo?: number | null;
  solo_propias?: boolean;
  limite?: number;
  pagina?: number;
}

export interface SearchCardsResponse {
  items: PokemonCard[];
  total: number;
  pagina: number;
  limite: number;
  total_paginas: number;
}

