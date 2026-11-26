"""Controlador del oponente Bot del servidor (US 3 y US 4)."""

import random
import secrets
from typing import Any

from src.modules.motor_juego.domain.modelos_partida import TAMANO_DECK_PARTIDA
from src.modules.partidas_emparejamiento.partidas.domain.partida_model import (
    ParticipantePartidaInput,
)
from src.modules.partidas_emparejamiento.partidas.ports.partida_ports import (
    FuenteCatalogoPartidaPort,
)

from ..domain.emparejamiento_model import BotCatalogoInsuficienteError


class ControladorBot:
    """Arma el participante Bot con 12 cartas distintas válidas del catálogo."""

    def __init__(self, catalogo: FuenteCatalogoPartidaPort) -> None:
        self._catalogo = catalogo

    async def construir_participante_bot(
        self,
        sesion: Any,
        *,
        elo_referencia: int,
        seat: int = 2,
    ) -> ParticipantePartidaInput:
        """Selecciona 12 cartas READY del catálogo para enfrentar al jugador."""
        elegibles = await self._catalogo.seleccionar_cartas_bot(sesion)
        por_id = {carta.id: carta for carta in elegibles}
        ids_ordenados = sorted(por_id)
        if len(ids_ordenados) < TAMANO_DECK_PARTIDA:
            raise BotCatalogoInsuficienteError(
                f"El catálogo solo tiene {len(ids_ordenados)} cartas elegibles para el Bot; "
                f"se requieren al menos {TAMANO_DECK_PARTIDA}."
            )

        rng = random.Random(secrets.randbits(64))
        seleccionadas = tuple(rng.sample(ids_ordenados, TAMANO_DECK_PARTIDA))
        return ParticipantePartidaInput(
            seat=seat,
            user_id=None,
            is_bot=True,
            deck_id=None,
            card_ids=seleccionadas,
            elo=elo_referencia,
        )
