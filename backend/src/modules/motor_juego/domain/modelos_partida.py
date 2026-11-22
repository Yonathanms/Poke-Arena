"""Modelos puros e inmutables del dominio de partidas (RNF-ARQ-01, RNF-SEG-05)."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

TOTAL_TURNOS_PARTIDA = 6
TURNOS_PARTIDA: frozenset[int] = frozenset(range(1, TOTAL_TURNOS_PARTIDA + 1))
CANTIDAD_UBICACIONES_PARTIDA = 3
MIN_UBICACIONES_JUGABLES = 2
TAMANO_DECK_PARTIDA = 12
MANO_INICIAL_CARTAS = 3
LIMITE_MANO_CARTAS = 7
CONTEXTOS_PARTIDA_VALIDOS: frozenset[str] = frozenset({"RANKED", "TOURNAMENT"})


class ErrorMotorJuego(Exception):
    """Error base puro del motor determinista de juego."""


class UbicacionesInsuficientesError(ErrorMotorJuego):
    """El catálogo no tiene al menos 3 ubicaciones con >= 2 jugables."""


class DeckPartidaInvalidoError(ErrorMotorJuego):
    """El deck del participante no cumple las 12 cartas distintas requeridas."""


class ParticipanteInvalidoError(ErrorMotorJuego):
    """Los participantes de la partida presentan asientos o identidades inválidas."""


class JugadorNoParticipaError(ErrorMotorJuego):
    """El usuario solicitante no es participante humano de la partida."""


class TurnoInvalidoError(ErrorMotorJuego):
    """El número de turno está fuera del rango oficial de la partida."""


def _congelar_valor(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return MappingProxyType({str(k): _congelar_valor(v) for k, v in valor.items()})
    if isinstance(valor, (list, tuple)):
        return tuple(_congelar_valor(item) for item in valor)
    return valor


def _descongelar_valor(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return {str(k): _descongelar_valor(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_descongelar_valor(item) for item in valor]
    return valor


def _congelar_mapping(datos: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(k): _congelar_valor(v) for k, v in datos.items()})


@dataclass(frozen=True, slots=True)
class CartaSnapshot:
    """Snapshot inmutable de una carta al inicio de la partida (RNF-INT-07)."""

    id: str
    code: str
    name: str
    cost: int
    power: int
    card_type: str
    rarity: str
    ability_code: str
    ability_name: str
    ability_params: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ability_params", _congelar_mapping(self.ability_params))

    def to_dict(self) -> dict[str, Any]:
        """Serializa el snapshot de carta a estructuras nativas JSON-compatibles."""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "cost": self.cost,
            "power": self.power,
            "card_type": self.card_type,
            "rarity": self.rarity,
            "ability_code": self.ability_code,
            "ability_name": self.ability_name,
            "ability_params": _descongelar_valor(self.ability_params),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CartaSnapshot":
        """Reconstruye un CartaSnapshot desde un diccionario persistido."""
        return cls(
            id=str(data["id"]),
            code=str(data["code"]),
            name=str(data["name"]),
            cost=int(data["cost"]),
            power=int(data["power"]),
            card_type=str(data["card_type"]),
            rarity=str(data["rarity"]),
            ability_code=str(data["ability_code"]),
            ability_name=str(data["ability_name"]),
            ability_params=data.get("ability_params") or {},
        )


@dataclass(frozen=True, slots=True)
class UbicacionSnapshot:
    """Snapshot inmutable de una ubicación seleccionada para la partida."""

    id: str
    nombre: str
    descripcion: str
    card_limit: int
    energia_tipo: str
    energia_valor: int
    efecto_tipo: str
    efecto_params: Mapping[str, Any]
    image_url: str
    thumbnail_url: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "efecto_params", _congelar_mapping(self.efecto_params))

    def to_dict(self) -> dict[str, Any]:
        """Serializa la ubicación a un diccionario JSON-compatible."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "card_limit": self.card_limit,
            "energia_tipo": self.energia_tipo,
            "energia_valor": self.energia_valor,
            "efecto_tipo": self.efecto_tipo,
            "efecto_params": _descongelar_valor(self.efecto_params),
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "UbicacionSnapshot":
        """Reconstruye un UbicacionSnapshot desde un diccionario persistido."""
        return cls(
            id=str(data["id"]),
            nombre=str(data["nombre"]),
            descripcion=str(data["descripcion"]),
            card_limit=int(data["card_limit"]),
            energia_tipo=str(data["energia_tipo"]),
            energia_valor=int(data["energia_valor"]),
            efecto_tipo=str(data["efecto_tipo"]),
            efecto_params=data.get("efecto_params") or {},
            image_url=str(data["image_url"]),
            thumbnail_url=str(data["thumbnail_url"]),
        )


@dataclass(frozen=True, slots=True)
class ParticipanteEntrada:
    """Datos de entrada inmutables de un participante para preparar la partida."""

    seat: int
    user_id: str | None
    is_bot: bool
    elo: int
    deck_cards: tuple[CartaSnapshot, ...]


@dataclass(frozen=True, slots=True)
class EstadoJugadorInterno:
    """Estado autoritativo interno de un jugador dentro de la partida."""

    seat: int
    user_id: str | None
    is_bot: bool
    deck_order: tuple[str, ...]
    draw_pile: tuple[str, ...]
    hand: tuple[str, ...]
    graveyard: tuple[str, ...]
    energy: int
    energy_base: int
    energy_bonus: int
    elo: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serializa el estado interno del jugador para almacenamiento JSONB."""
        return {
            "seat": self.seat,
            "user_id": self.user_id,
            "is_bot": self.is_bot,
            "deck_order": list(self.deck_order),
            "draw_pile": list(self.draw_pile),
            "hand": list(self.hand),
            "graveyard": list(self.graveyard),
            "energy": self.energy,
            "energy_base": self.energy_base,
            "energy_bonus": self.energy_bonus,
            "elo": self.elo,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EstadoJugadorInterno":
        """Reconstruye el estado interno del jugador desde un diccionario JSONB."""
        raw_user_id = data.get("user_id")
        return cls(
            seat=int(data["seat"]),
            user_id=str(raw_user_id) if raw_user_id is not None else None,
            is_bot=bool(data["is_bot"]),
            deck_order=tuple(str(cid) for cid in data["deck_order"]),
            draw_pile=tuple(str(cid) for cid in data["draw_pile"]),
            hand=tuple(str(cid) for cid in data["hand"]),
            graveyard=tuple(str(cid) for cid in data["graveyard"]),
            energy=int(data["energy"]),
            energy_base=int(data["energy_base"]),
            energy_bonus=int(data["energy_bonus"]),
            elo=int(data.get("elo", 0)),
        )


@dataclass(frozen=True, slots=True)
class EstadoPartidaInterno:
    """Estado interno completo de la partida (nunca expuesto directamente al cliente)."""

    seed: int
    turn_number: int
    bet_cubes: int
    locations: tuple[UbicacionSnapshot, ...]
    cards_catalog: Mapping[str, CartaSnapshot]
    board: Mapping[str, Mapping[int, tuple[str, ...]]]
    players: tuple[EstadoJugadorInterno, EstadoJugadorInterno]
    context: str = "RANKED"

    def __post_init__(self) -> None:
        catalogo_congelado = MappingProxyType(
            {str(cid): carta for cid, carta in self.cards_catalog.items()}
        )
        tablero_congelado = MappingProxyType({
            str(loc_id): MappingProxyType({
                int(seat): tuple(str(cid) for cid in cartas)
                for seat, cartas in por_asiento.items()
            })
            for loc_id, por_asiento in self.board.items()
        })
        object.__setattr__(self, "cards_catalog", catalogo_congelado)
        object.__setattr__(self, "board", tablero_congelado)

    def locations_snapshot_dict(self) -> list[dict[str, Any]]:
        """Serializa las 3 ubicaciones elegidas para matches.locations_snapshot."""
        return [loc.to_dict() for loc in self.locations]

    def deck_orders_snapshot_dict(self) -> dict[str, list[str]]:
        """Serializa el orden barajado exacto por asiento para replay."""
        return {str(player.seat): list(player.deck_order) for player in self.players}

    def to_state_dict(self) -> dict[str, Any]:
        """Serializa el estado autoritativo completo de la partida para matches.state_json."""
        return {
            "seed": self.seed,
            "context": self.context,
            "turn_number": self.turn_number,
            "bet_cubes": self.bet_cubes,
            "locations": self.locations_snapshot_dict(),
            "cards_catalog": {
                cid: carta.to_dict() for cid, carta in self.cards_catalog.items()
            },
            "board": {
                loc_id: {str(seat): list(cartas) for seat, cartas in por_asiento.items()}
                for loc_id, por_asiento in self.board.items()
            },
            "players": [player.to_dict() for player in self.players],
        }

    @classmethod
    def from_state_dict(cls, data: Mapping[str, Any]) -> "EstadoPartidaInterno":
        """Reconstruye el estado interno completo desde matches.state_json."""
        raw_players = data["players"]
        if len(raw_players) != 2:
            raise ParticipanteInvalidoError(
                "El estado persistido debe contener exactamente 2 jugadores."
            )
        return cls(
            seed=int(data["seed"]),
            context=str(data.get("context", "RANKED")),
            turn_number=int(data["turn_number"]),
            bet_cubes=int(data["bet_cubes"]),
            locations=tuple(UbicacionSnapshot.from_dict(loc) for loc in data["locations"]),
            cards_catalog={
                str(cid): CartaSnapshot.from_dict(carta)
                for cid, carta in data["cards_catalog"].items()
            },
            board={
                str(loc_id): {
                    int(seat): tuple(str(cid) for cid in cartas)
                    for seat, cartas in por_asiento.items()
                }
                for loc_id, por_asiento in data["board"].items()
            },
            players=(
                EstadoJugadorInterno.from_dict(raw_players[0]),
                EstadoJugadorInterno.from_dict(raw_players[1]),
            ),
        )


@dataclass(frozen=True, slots=True)
class VistaEnergia:
    """Resumen de energía disponible para el jugador en el turno actual."""

    total: int
    base: int
    bonus: int

    def to_dict(self) -> dict[str, int]:
        return {"total": self.total, "base": self.base, "bonus": self.bonus}


@dataclass(frozen=True, slots=True)
class VistaUbicacionPublica:
    """Proyección pública de una ubicación y las cartas reveladas en su tablero."""

    location: UbicacionSnapshot
    my_cards: tuple[CartaSnapshot, ...]
    opponent_cards: tuple[CartaSnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.location.to_dict(),
            "my_cards": [c.to_dict() for c in self.my_cards],
            "opponent_cards": [c.to_dict() for c in self.opponent_cards],
        }


@dataclass(frozen=True, slots=True)
class VistaRivalPublica:
    """Información pública del oponente bajo Fog of War (RNF-SEG-05)."""

    seat: int
    is_bot: bool
    elo: int
    hand_count: int
    deck_remaining: int
    graveyard: tuple[CartaSnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seat": self.seat,
            "is_bot": self.is_bot,
            "elo": self.elo,
            "hand_count": self.hand_count,
            "deck_remaining": self.deck_remaining,
            "graveyard": [c.to_dict() for c in self.graveyard],
        }


@dataclass(frozen=True, slots=True)
class VistaPartidaJugador:
    """Vista autoritativa filtrada para un participante (nunca expone mazo ni mano rival)."""

    context: str
    turn_number: int
    bet_cubes: int
    my_seat: int
    locations: tuple[VistaUbicacionPublica, ...]
    my_hand: tuple[CartaSnapshot, ...]
    my_deck_remaining: int
    my_graveyard: tuple[CartaSnapshot, ...]
    my_energy: VistaEnergia
    opponent: VistaRivalPublica

    def to_dict(self) -> dict[str, Any]:
        """Serializa la vista Fog of War del jugador a un payload DTO puro."""
        return {
            "context": self.context,
            "turn_number": self.turn_number,
            "bet_cubes": self.bet_cubes,
            "my_seat": self.my_seat,
            "locations": [loc.to_dict() for loc in self.locations],
            "my_hand": [carta.to_dict() for carta in self.my_hand],
            "my_deck_remaining": self.my_deck_remaining,
            "my_graveyard": [carta.to_dict() for carta in self.my_graveyard],
            "my_energy": self.my_energy.to_dict(),
            "opponent": self.opponent.to_dict(),
        }


__all__ = [
    "CANTIDAD_UBICACIONES_PARTIDA",
    "CONTEXTOS_PARTIDA_VALIDOS",
    "CartaSnapshot",
    "DeckPartidaInvalidoError",
    "ErrorMotorJuego",
    "EstadoJugadorInterno",
    "EstadoPartidaInterno",
    "JugadorNoParticipaError",
    "LIMITE_MANO_CARTAS",
    "MANO_INICIAL_CARTAS",
    "MIN_UBICACIONES_JUGABLES",
    "ParticipanteEntrada",
    "ParticipanteInvalidoError",
    "TAMANO_DECK_PARTIDA",
    "TOTAL_TURNOS_PARTIDA",
    "TURNOS_PARTIDA",
    "TurnoInvalidoError",
    "UbicacionSnapshot",
    "UbicacionesInsuficientesError",
    "VistaEnergia",
    "VistaPartidaJugador",
    "VistaRivalPublica",
    "VistaUbicacionPublica",
]
