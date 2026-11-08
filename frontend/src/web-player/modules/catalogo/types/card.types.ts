export type CardType = 'FUE' | 'AGU' | 'PLA' | 'ELE' | 'PSI' | 'LUC' | 'INC';
export type CardRarity = 'COMUN' | 'INFRECUENTE' | 'RARA' | 'EPICA' | 'LEGENDARIA';

export interface PokemonCard {
  id: string;
  name: string;
  code: string;
  type: CardType;
  rarity: CardRarity;
  cost: number;
  power: number;
  hp: number;
  imageUrl: string;
  description?: string;
  price?: number;
}

