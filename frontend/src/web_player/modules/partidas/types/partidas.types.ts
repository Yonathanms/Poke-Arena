/** Contratos DTO y utilidades puras de presentación para la Arena y Partidas (Fase 4). */

import { ApiHttpError } from "../../../../shared/services/http-client";

export type MatchContext = "RANKED" | "TOURNAMENT";

export type MatchSearchStatus = "SEARCHING" | "MATCHED" | "CANCELLED" | "EXPIRED";

export interface MatchSearchDTO {
  readonly search_id: string;
  readonly status: MatchSearchStatus;
  readonly context: MatchContext;
  readonly deck_id: string | null;
  readonly elo_snapshot: number;
  readonly match_id: string | null;
  readonly elapsed_seconds: number;
  readonly bot_offer_available: boolean;
  readonly bot_offer_in_seconds: number;
  readonly state_version: number;
  readonly created_at: string;
  readonly last_seen_at: string;
  readonly warning_code?: string | null;
  readonly warning_detail?: string | null;
}

export interface ActiveMatchSummaryDTO {
  readonly match_id: string;
  readonly context: MatchContext;
  readonly status: string;
  readonly is_bot_match: boolean;
  readonly bet_cubes: number;
  readonly turn_number: number;
  readonly turn_duration_seconds: number;
  readonly turn_started_at: string;
  readonly turn_ends_at: string;
  readonly state_version: number;
}

export interface MatchCardDTO {
  readonly id: string;
  readonly code: string;
  readonly name: string;
  readonly cost: number;
  readonly power: number;
  readonly card_type: string;
  readonly rarity: string;
  readonly ability_code: string;
  readonly ability_name: string;
  readonly ability_params: Readonly<Record<string, unknown>>;
}

export interface MatchLocationDTO {
  readonly id: string;
  readonly nombre: string;
  readonly descripcion: string;
  readonly card_limit: number;
  readonly energia_tipo: string;
  readonly energia_valor: number;
  readonly efecto_tipo: string;
  readonly efecto_params: Readonly<Record<string, unknown>>;
  readonly image_url: string;
  readonly thumbnail_url: string;
  readonly my_cards: readonly MatchCardDTO[];
  readonly opponent_cards: readonly MatchCardDTO[];
}

export interface MatchEnergyDTO {
  readonly total: number;
  readonly base: number;
  readonly bonus: number;
}

export interface MatchOpponentDTO {
  readonly seat: number;
  readonly is_bot: boolean;
  readonly elo: number;
  readonly hand_count: number;
  readonly deck_remaining: number;
  readonly graveyard: readonly MatchCardDTO[];
}

export interface ActiveMatchViewDTO {
  readonly match_id: string;
  readonly status: string;
  readonly context: MatchContext;
  readonly is_bot_match: boolean;
  readonly bet_cubes: number;
  readonly turn_number: number;
  readonly turn_duration_seconds: number;
  readonly turn_started_at: string;
  readonly turn_ends_at: string;
  readonly state_version: number;
  readonly my_seat: number;
  readonly locations: readonly MatchLocationDTO[];
  readonly my_hand: readonly MatchCardDTO[];
  readonly my_deck_remaining: number;
  readonly my_graveyard: readonly MatchCardDTO[];
  readonly my_energy: MatchEnergyDTO;
  readonly opponent: MatchOpponentDTO;
}

export interface ArenaUiError {
  readonly title: string;
  readonly message: string;
}

const TYPE_LABELS: Readonly<Record<string, string>> = {
  FUE: "Fuego",
  AGU: "Agua",
  PLA: "Planta",
  ELE: "Eléctrico",
  PSI: "Psíquico",
  LUC: "Lucha",
};

export function formatLocationEffectSummary(location: MatchLocationDTO): string {
  const params = location.efecto_params ?? {};
  if (location.efecto_tipo === "BONIFICACION_POR_TIPO") {
    const rawType = typeof params.tipo === "string" ? params.tipo : "";
    const tipoLabel = TYPE_LABELS[rawType] ?? rawType;
    const cantidad = typeof params.cantidad === "number" ? params.cantidad : 0;
    const signo = cantidad >= 0 ? `+${cantidad}` : `${cantidad}`;
    return `${signo} de poder a cartas ${tipoLabel}`.trim();
  }
  if (location.efecto_tipo === "MODIFICADOR_COSTO") {
    const cantidad = typeof params.cantidad === "number" ? params.cantidad : 0;
    const signo = cantidad >= 0 ? `+${cantidad}` : `${cantidad}`;
    const rawType = typeof params.tipo === "string" ? params.tipo : "";
    const scope = rawType ? `a cartas ${TYPE_LABELS[rawType] ?? rawType}` : "a todas las cartas";
    return `Costo ${signo} ${scope}`;
  }
  if (location.efecto_tipo === "RESTRICCION_TURNO") {
    const turnos = Array.isArray(params.turnos)
      ? params.turnos.filter((t): t is number => typeof t === "number")
      : [];
    if (turnos.length === 0) return "Restricción por turno";
    return turnos.length === 1
      ? `No se puede jugar en el turno ${turnos[0]}`
      : `Bloqueada en turnos ${turnos.join(", ")}`;
  }
  return "Estadio sin restricción especial";
}

export function formatElapsedClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function translateArenaError(err: unknown): ArenaUiError {
  if (err instanceof ApiHttpError) {
    switch (err.code) {
      case "cubos_insuficientes":
        return {
          title: "Cubos de energía insuficientes",
          message: err.detail,
        };
      case "partida_activa":
        return {
          title: "Combate en curso",
          message: "Ya tienes una partida activa. Reanúdala para continuar jugando.",
        };
      case "busqueda_vigente_otro_contexto":
        return {
          title: "Búsqueda abierta en otro modo",
          message: "Ya estás buscando rival en otro modo. Cancela la búsqueda actual para cambiar.",
        };
      case "busqueda_ya_emparejada":
        return {
          title: "¡Rival encontrado!",
          message: "Tu combate acaba de comenzar. Te estamos llevando al tablero.",
        };
      case "oferta_bot_no_disponible":
        return {
          title: "Bot en espera",
          message: "El Bot de la Arena estará disponible tras completar 60 segundos de búsqueda.",
        };
      case "deck_requerido":
        return {
          title: "Mazo requerido",
          message: "Selecciona un mazo completo de 12 cartas antes de entrar a la Arena.",
        };
      case "deck_no_encontrado":
      case "deck_invalido":
        return {
          title: "Mazo no válido",
          message: "El mazo elegido no está completo o contiene cartas que ya no posees.",
        };
      case "bot_catalogo_insuficiente":
        return {
          title: "Bot de la Arena no disponible",
          message: "El Bot de la Arena aún se está preparando. Intenta nuevamente más tarde.",
        };
      case "paquete_sin_abrir":
        return {
          title: "Paquete inicial pendiente",
          message: "Abre tu paquete inicial de entrenador para poder combatir en la Arena.",
        };
      case "ubicaciones_insuficientes":
        return {
          title: "Estadios en preparación",
          message: "Todavía no hay suficientes estadios jugables habilitados en la Arena.",
        };
      default:
        return {
          title: "Aviso de la Arena",
          message: err.isNetworkError
            ? "No pudimos comunicarnos con la Arena. Revisa tu conexión e intenta de nuevo."
            : "No se pudo completar la acción en la Arena. Intenta nuevamente en unos segundos.",
        };
    }
  }

  return {
    title: "Aviso de la Arena",
    message: "Ocurrió un inconveniente inesperado. Intenta nuevamente en unos instantes.",
  };
}
