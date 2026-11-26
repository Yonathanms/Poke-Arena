"""Preparación determinista de inicio de partida y proyección Fog of War (US 4)."""

import random
from collections.abc import Mapping, Sequence
from typing import Any

from .modelos_partida import (
    CANTIDAD_UBICACIONES_PARTIDA,
    CONTEXTOS_PARTIDA_VALIDOS,
    LIMITE_MANO_CARTAS,
    MANO_INICIAL_CARTAS,
    MIN_UBICACIONES_JUGABLES,
    TAMANO_DECK_PARTIDA,
    TOTAL_TURNOS_PARTIDA,
    CartaSnapshot,
    DeckPartidaInvalidoError,
    EstadoJugadorInterno,
    EstadoPartidaInterno,
    JugadorNoParticipaError,
    ParticipanteEntrada,
    ParticipanteInvalidoError,
    TurnoInvalidoError,
    UbicacionesInsuficientesError,
    UbicacionSnapshot,
    VistaEnergia,
    VistaPartidaJugador,
    VistaRivalPublica,
    VistaUbicacionPublica,
)
from .strategies.efectos_ubicacion import (
    REGISTRO_ESTRATEGIAS_POR_DEFECTO,
    RegistroEstrategiasUbicacion,
    calcular_energia_extra_ubicacion,
    es_ubicacion_jugable,
)


def energia_base_turno(turno: int) -> int:
    """Devuelve la energía base no acumulable del turno (2..7 para turnos 1..6)."""
    if isinstance(turno, bool) or not isinstance(turno, int):
        raise TurnoInvalidoError(f"El turno debe ser entero; se recibió {turno!r}.")
    if not 1 <= turno <= TOTAL_TURNOS_PARTIDA:
        raise TurnoInvalidoError(
            f"El turno {turno} está fuera del rango permitido (1..{TOTAL_TURNOS_PARTIDA})."
        )
    return turno + 1


def calcular_energia_turno(
    turno: int,
    ubicaciones: Sequence[UbicacionSnapshot],
    cartas_propias_por_ubicacion: Mapping[str, int] | None = None,
    *,
    registro: RegistroEstrategiasUbicacion | None = None,
) -> tuple[int, int, int]:
    """Calcula (total, base, bonus) sumando energía base del turno y bonos de ubicaciones."""
    base = energia_base_turno(turno)
    conteo = cartas_propias_por_ubicacion or {}
    bonus = sum(
        calcular_energia_extra_ubicacion(
            ubicacion,
            conteo.get(ubicacion.id, 0),
            registro=registro,
        )
        for ubicacion in ubicaciones
    )
    return base + bonus, base, bonus


def seleccionar_ubicaciones(
    candidatas: Sequence[UbicacionSnapshot],
    rng: random.Random,
    *,
    registro: RegistroEstrategiasUbicacion | None = None,
) -> tuple[UbicacionSnapshot, UbicacionSnapshot, UbicacionSnapshot]:
    """Elige al azar 3 ubicaciones distintas garantizando al menos 2 jugables."""
    por_id = {ubicacion.id: ubicacion for ubicacion in candidatas}
    canonicas = [por_id[loc_id] for loc_id in sorted(por_id)]
    if len(canonicas) < CANTIDAD_UBICACIONES_PARTIDA:
        raise UbicacionesInsuficientesError(
            f"Se requieren al menos {CANTIDAD_UBICACIONES_PARTIDA} ubicaciones distintas "
            f"en el catálogo; hay {len(canonicas)}."
        )

    reg = registro if registro is not None else REGISTRO_ESTRATEGIAS_POR_DEFECTO
    jugables = [u for u in canonicas if es_ubicacion_jugable(u, registro=reg)]
    if len(jugables) < MIN_UBICACIONES_JUGABLES:
        raise UbicacionesInsuficientesError(
            f"Se requieren al menos {MIN_UBICACIONES_JUGABLES} ubicaciones jugables "
            f"(con límite mayor a 0 y algún turno habilitado); hay {len(jugables)}."
        )

    elegidas_jugables = rng.sample(jugables, MIN_UBICACIONES_JUGABLES)
    elegidas_ids = {u.id for u in elegidas_jugables}
    restantes = [u for u in canonicas if u.id not in elegidas_ids]
    tercera = rng.choice(restantes)
    seleccionadas = [elegidas_jugables[0], elegidas_jugables[1], tercera]
    rng.shuffle(seleccionadas)
    return (seleccionadas[0], seleccionadas[1], seleccionadas[2])


def barajar_deck(card_ids: Sequence[str], rng: random.Random) -> tuple[str, ...]:
    """Baraja con Fisher-Yates sobre orden canónico previo para independencia de SQL."""
    baraja = sorted(card_ids)
    for indice in range(len(baraja) - 1, 0, -1):
        destino = rng.randint(0, indice)
        baraja[indice], baraja[destino] = baraja[destino], baraja[indice]
    return tuple(baraja)


def robar_carta(
    hand: tuple[str, ...],
    draw_pile: tuple[str, ...],
    *,
    limite_mano: int = LIMITE_MANO_CARTAS,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Roba la siguiente carta del mazo si hay disponibles y la mano no llegó al límite."""
    if len(hand) >= limite_mano or not draw_pile:
        return hand, draw_pile
    return hand + (draw_pile[0],), draw_pile[1:]


def _validar_participantes(
    jugador_1: ParticipanteEntrada,
    jugador_2: ParticipanteEntrada,
) -> None:
    if jugador_1.seat != 1 or jugador_2.seat != 2:
        raise ParticipanteInvalidoError("Los participantes deben ocupar los asientos 1 y 2.")
    for jugador in (jugador_1, jugador_2):
        if isinstance(jugador.elo, bool) or not isinstance(jugador.elo, int):
            raise ParticipanteInvalidoError("El Elo del participante debe ser un entero.")
        if jugador.is_bot and jugador.user_id is not None:
            raise ParticipanteInvalidoError("El participante Bot debe tener user_id=None.")
        if not jugador.is_bot and (not isinstance(jugador.user_id, str) or not jugador.user_id):
            raise ParticipanteInvalidoError("Todo participante humano requiere user_id no vacío.")
        if len(jugador.deck_cards) != TAMANO_DECK_PARTIDA:
            raise DeckPartidaInvalidoError(
                f"El deck del asiento {jugador.seat} debe tener {TAMANO_DECK_PARTIDA} cartas; "
                f"recibidas {len(jugador.deck_cards)}."
            )
        ids_unicos = {carta.id for carta in jugador.deck_cards}
        if len(ids_unicos) != TAMANO_DECK_PARTIDA:
            raise DeckPartidaInvalidoError(
                f"El deck del asiento {jugador.seat} contiene cartas repetidas."
            )
    if (
        not jugador_1.is_bot
        and not jugador_2.is_bot
        and jugador_1.user_id == jugador_2.user_id
    ):
        raise ParticipanteInvalidoError("Ambos asientos no pueden pertenecer al mismo jugador.")


def _preparar_jugador(
    participante: ParticipanteEntrada,
    rng: random.Random,
    energia_inicial: tuple[int, int, int],
) -> EstadoJugadorInterno:
    orden_barajado = barajar_deck([c.id for c in participante.deck_cards], rng)
    mano_inicial = orden_barajado[:MANO_INICIAL_CARTAS]
    mazo_restante = orden_barajado[MANO_INICIAL_CARTAS:]
    mano_turno_1, mazo_turno_1 = robar_carta(mano_inicial, mazo_restante)
    energy_total, energy_base, energy_bonus = energia_inicial
    return EstadoJugadorInterno(
        seat=participante.seat,
        user_id=participante.user_id,
        is_bot=participante.is_bot,
        deck_order=orden_barajado,
        draw_pile=mazo_turno_1,
        hand=mano_turno_1,
        graveyard=(),
        energy=energy_total,
        energy_base=energy_base,
        energy_bonus=energy_bonus,
        elo=participante.elo,
    )


def preparar_inicio_partida(
    seed: int,
    context: str,
    bet_cubes: int,
    ubicaciones_candidatas: Sequence[UbicacionSnapshot],
    jugador_1: ParticipanteEntrada,
    jugador_2: ParticipanteEntrada,
    *,
    registro: RegistroEstrategiasUbicacion | None = None,
) -> EstadoPartidaInterno:
    """Prepara de forma pura y determinista el estado inicial de Turno 1 de una partida."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("La semilla seed debe ser un entero.")
    if context not in CONTEXTOS_PARTIDA_VALIDOS:
        raise ValueError(f"Contexto de partida no válido: {context!r}.")
    if isinstance(bet_cubes, bool) or not isinstance(bet_cubes, int) or bet_cubes < 0:
        raise ValueError("bet_cubes debe ser un entero mayor o igual a 0.")

    _validar_participantes(jugador_1, jugador_2)
    reg = registro if registro is not None else REGISTRO_ESTRATEGIAS_POR_DEFECTO
    rng = random.Random(seed)

    ubicaciones = seleccionar_ubicaciones(ubicaciones_candidatas, rng, registro=reg)
    energia_t1 = calcular_energia_turno(1, ubicaciones, registro=reg)

    estado_j1 = _preparar_jugador(jugador_1, rng, energia_t1)
    estado_j2 = _preparar_jugador(jugador_2, rng, energia_t1)

    catalogo: dict[str, CartaSnapshot] = {}
    for carta in (*jugador_1.deck_cards, *jugador_2.deck_cards):
        catalogo[carta.id] = carta

    tablero_inicial: dict[str, dict[int, tuple[str, ...]]] = {
        ubicacion.id: {1: (), 2: ()} for ubicacion in ubicaciones
    }

    return EstadoPartidaInterno(
        seed=seed,
        context=context,
        turn_number=1,
        bet_cubes=bet_cubes,
        locations=ubicaciones,
        cards_catalog=catalogo,
        board=tablero_inicial,
        players=(estado_j1, estado_j2),
    )


def _resolver_cartas(
    catalogo: Mapping[str, CartaSnapshot],
    card_ids: Sequence[str],
) -> tuple[CartaSnapshot, ...]:
    return tuple(catalogo[cid] for cid in card_ids)


def construir_vista_jugador(
    estado: EstadoPartidaInterno,
    viewer_user_id: str,
) -> VistaPartidaJugador:
    """Proyecta el estado interno aplicando Fog of War estricto para el usuario solicitante."""
    if not viewer_user_id:
        raise JugadorNoParticipaError("Se requiere un identificador de jugador válido.")

    p1, p2 = estado.players
    if not p1.is_bot and p1.user_id == viewer_user_id:
        propio, rival = p1, p2
    elif not p2.is_bot and p2.user_id == viewer_user_id:
        propio, rival = p2, p1
    else:
        raise JugadorNoParticipaError(
            f"El usuario {viewer_user_id!r} no participa en esta partida."
        )

    ubicaciones_publicas = tuple(
        VistaUbicacionPublica(
            location=ubicacion,
            my_cards=_resolver_cartas(
                estado.cards_catalog,
                estado.board.get(ubicacion.id, {}).get(propio.seat, ()),
            ),
            opponent_cards=_resolver_cartas(
                estado.cards_catalog,
                estado.board.get(ubicacion.id, {}).get(rival.seat, ()),
            ),
        )
        for ubicacion in estado.locations
    )

    return VistaPartidaJugador(
        context=estado.context,
        turn_number=estado.turn_number,
        bet_cubes=estado.bet_cubes,
        my_seat=propio.seat,
        locations=ubicaciones_publicas,
        my_hand=_resolver_cartas(estado.cards_catalog, propio.hand),
        my_deck_remaining=len(propio.draw_pile),
        my_graveyard=_resolver_cartas(estado.cards_catalog, propio.graveyard),
        my_energy=VistaEnergia(
            total=propio.energy,
            base=propio.energy_base,
            bonus=propio.energy_bonus,
        ),
        opponent=VistaRivalPublica(
            seat=rival.seat,
            is_bot=rival.is_bot,
            elo=rival.elo,
            hand_count=len(rival.hand),
            deck_remaining=len(rival.draw_pile),
            graveyard=_resolver_cartas(estado.cards_catalog, rival.graveyard),
        ),
    )


def proyectar_vista_jugador(
    estado: EstadoPartidaInterno,
    viewer_user_id: str,
) -> dict[str, Any]:
    """Devuelve el diccionario filtrado por Fog of War para un participante de la partida."""
    return construir_vista_jugador(estado, viewer_user_id).to_dict()


class MotorJuegoDeterminista:
    """Implementación pura del puerto MotorJuegoPort."""

    def __init__(self, registro: RegistroEstrategiasUbicacion | None = None) -> None:
        self._registro = registro

    def preparar_inicio_partida(
        self,
        *,
        seed: int,
        context: str,
        bet_cubes: int,
        ubicaciones_candidatas: Sequence[UbicacionSnapshot],
        jugador_1: ParticipanteEntrada,
        jugador_2: ParticipanteEntrada,
    ) -> EstadoPartidaInterno:
        return preparar_inicio_partida(
            seed=seed,
            context=context,
            bet_cubes=bet_cubes,
            ubicaciones_candidatas=ubicaciones_candidatas,
            jugador_1=jugador_1,
            jugador_2=jugador_2,
            registro=self._registro,
        )

    def proyectar_vista_jugador(
        self,
        estado: EstadoPartidaInterno,
        viewer_user_id: str,
    ) -> dict[str, Any]:
        return proyectar_vista_jugador(estado, viewer_user_id)


__all__ = [
    "MotorJuegoDeterminista",
    "barajar_deck",
    "calcular_energia_turno",
    "construir_vista_jugador",
    "energia_base_turno",
    "preparar_inicio_partida",
    "proyectar_vista_jugador",
    "robar_carta",
    "seleccionar_ubicaciones",
]
