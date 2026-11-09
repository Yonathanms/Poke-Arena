/**
 * Servicio HTTP para la búsqueda y consulta de cartas en el Catálogo (`cards.api.ts`).
 *
 * Responsabilidades:
 * 1. Consumir el endpoint real de FastAPI: `GET /api/v1/content/cards`.
 * 2. Transmitir los filtros de consulta validados: `q`, `tipo`, `rareza`, `limite` y `pagina`.
 * 3. Procesar y tipar la respuesta paginada estructurada (`SearchCardsResponse`).
 * 4. Propagar fielmente errores de transporte y aplicación (`ApiHttpError`),
 *    incluyendo `503 catalogo_no_disponible` y `401`.
 */

import {
  requestApiWithMeta,
  type ApiResponse,
} from "../../../../shared/services/http-client";
import { ensureAuthHttpBridgeConfigured } from "../../../../web_admin/modules/auth/services/auth.api";
import type {
  CardRarity,
  CardType,
  PokemonCard,
  SearchCardsParams,
  SearchCardsResponse,
} from "../types/card.types";

const CARDS_ENDPOINT = "/content/cards";

export async function fetchCardThumbnail(id: string, signal: AbortSignal): Promise<Blob> {
  ensureAuthHttpBridgeConfigured();
  const { data } = await requestApiWithMeta<Blob>(
    `${CARDS_ENDPOINT}/${encodeURIComponent(id)}/thumbnail`,
    { signal, headers: { Accept: "image/webp" } },
    (response) => response.blob(),
  );
  if (data.type !== "image/webp" || data.size === 0) {
    throw new Error("La miniatura recibida no es un WebP válido.");
  }
  return data;
}

export interface CardApiRequestOptions {
  readonly fetchImpl?: typeof fetch;
  readonly signal?: AbortSignal;
  readonly baseUrl?: string;
}

const CANONICAL_TYPES: ReadonlySet<string> = new Set<CardType>([
  "FUE",
  "AGU",
  "PLA",
  "ELE",
  "PSI",
  "LUC",
]);

const CANONICAL_RARITIES: ReadonlySet<string> = new Set<CardRarity>([
  "COMUN",
  "POCO_COMUN",
  "RARA",
  "LEGENDARIA",
]);

/**
 * Normaliza y valida una carta individual proveniente de la API.
 */
function normalizePokemonCard(item: unknown): PokemonCard {
  if (typeof item !== "object" || item === null) {
    throw new Error("Elemento de carta inválido en la respuesta del catálogo.");
  }

  const raw = item as Record<string, unknown>;

  const id = String(raw.id ?? "");
  const name = String(raw.name ?? raw.nombre ?? "");
  const code = String(raw.code ?? raw.codigo ?? "");
  const rawType = String(raw.type ?? raw.tipo ?? raw.card_type ?? "FUE").toUpperCase();
  const rawRarity = String(raw.rarity ?? raw.rareza ?? "COMUN").toUpperCase();

  const type: CardType = CANONICAL_TYPES.has(rawType) ? (rawType as CardType) : "FUE";
  const rarity: CardRarity = CANONICAL_RARITIES.has(rawRarity)
    ? (rawRarity as CardRarity)
    : "COMUN";

  return {
    id,
    name,
    code,
    type,
    rarity,
    cost: typeof raw.cost === "number" ? raw.cost : Number(raw.coste_energia ?? 0),
    power: typeof raw.power === "number" ? raw.power : Number(raw.puntos_ataque ?? 0),
    hp: typeof raw.hp === "number" ? raw.hp : Number(raw.puntos_vida ?? 100),
    imageUrl: typeof raw.imageUrl === "string" ? raw.imageUrl : (raw.imagen_url as string | null) ?? null,
    thumbnailUrl:
      typeof raw.thumbnailUrl === "string"
        ? raw.thumbnailUrl
        : (raw.imagen_miniatura_url as string | null) ?? null,
    description:
      typeof raw.description === "string"
        ? raw.description
        : (raw.descripcion as string | null) ?? null,
    price: typeof raw.price === "number" ? raw.price : null,
    activo: typeof raw.activo === "boolean" ? raw.activo : true,
    ability_code: typeof raw.ability_code === "string" ? raw.ability_code : null,
  };
}

/**
 * Consulta cartas del catálogo real aplicando filtros de texto, tipo, rareza y paginación.
 */
export async function searchCards(
  params: SearchCardsParams = {},
  options: CardApiRequestOptions = {}
): Promise<ApiResponse<SearchCardsResponse>> {
  ensureAuthHttpBridgeConfigured();

  const query: Record<string, string | number> = {
    limite: Math.max(1, Math.min(100, params.limite ?? 15)),
    pagina: Math.max(1, params.pagina ?? 1),
  };

  if (params.q !== undefined && params.q !== null) {
    const trimmed = params.q.trim();
    if (trimmed.length > 0) {
      query.q = trimmed;
    }
  }

  if (params.tipo && CANONICAL_TYPES.has(params.tipo)) {
    query.tipo = params.tipo;
  }

  if (params.rareza && CANONICAL_RARITIES.has(params.rareza)) {
    query.rareza = params.rareza;
  }

  const searchParams = new URLSearchParams();
  searchParams.set("limite", String(query.limite));
  searchParams.set("pagina", String(query.pagina));
  if (query.q) {
    searchParams.set("q", String(query.q));
  }
  if (query.tipo) {
    searchParams.set("tipo", String(query.tipo));
  }
  if (query.rareza) {
    searchParams.set("rareza", String(query.rareza));
  }

  const endpoint = `${CARDS_ENDPOINT}?${searchParams.toString()}`;

  const response = await requestApiWithMeta<unknown>(endpoint, {
    method: "GET",
    requiresAuth: true,
    fetchImpl: options.fetchImpl,
    signal: options.signal,
    baseUrl: options.baseUrl,
  });

  const payload = response.data;
  if (typeof payload !== "object" || payload === null) {
    throw new Error("Respuesta inválida del servidor: cuerpo no es un objeto.");
  }

  const rawObj = payload as Record<string, unknown>;
  const rawItems = Array.isArray(rawObj.items) ? rawObj.items : [];
  const items = rawItems.map(normalizePokemonCard);
  const total = typeof rawObj.total === "number" ? rawObj.total : items.length;
  const pagina = typeof rawObj.pagina === "number" ? rawObj.pagina : query.pagina as number;
  const limite = typeof rawObj.limite === "number" ? rawObj.limite : query.limite as number;
  const totalPaginas =
    typeof rawObj.total_paginas === "number"
      ? rawObj.total_paginas
      : Math.max(1, Math.ceil(total / limite));

  const parsedResponse: SearchCardsResponse = {
    items,
    total,
    pagina,
    limite,
    total_paginas: totalPaginas,
  };

  return {
    ...response,
    data: parsedResponse,
  };
}
