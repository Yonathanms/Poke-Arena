"""Caso de uso de creación transaccional y consulta cacheada de partidas (US 4)."""

import json
import secrets
from typing import Any
from uuid import uuid4

from src.modules.motor_juego.domain.modelos_partida import (
    EstadoPartidaInterno,
    ParticipanteEntrada,
)
from src.modules.motor_juego.ports.motor_ports import MotorJuegoPort
from src.shared.cache import CachePort
from src.shared.http_etag import coincide_if_none_match, generar_etag

from ..domain.partida_model import (
    CatalogoPartidaInvalidoError,
    ParticipantePartidaInput,
    PartidaActivaResumen,
    PartidaCreada,
    PartidaNoEncontradaError,
    ResultadoVistaPartida,
)
from ..ports.partida_ports import FuenteCatalogoPartidaPort, RepositorioPartidasPort

_TTL_VISTA_PARTIDA = 300


def _clave_version_partida(match_id: str) -> str:
    return f"match:v1:{match_id}:ver"


def _clave_vista_usuario(match_id: str, version: int, user_id: str) -> str:
    return f"match:v1:{match_id}:v{version}:u:{user_id}"


class PartidasService:
    """Orquesta inicio determinista ACID y proyección Fog of War con caché ADR-003."""

    def __init__(
        self,
        repo: RepositorioPartidasPort,
        catalogo: FuenteCatalogoPartidaPort,
        motor: MotorJuegoPort,
        cache: CachePort,
        *,
        turn_duration_seconds: int = 30,
        ranked_initial_bet: int = 4,
    ) -> None:
        self._repo = repo
        self._catalogo = catalogo
        self._motor = motor
        self._cache = cache
        self._turn_duration_seconds = turn_duration_seconds
        self._ranked_initial_bet = ranked_initial_bet

    async def iniciar_partida_en_transaccion(
        self,
        sesion: Any,
        *,
        context: str,
        is_bot_match: bool,
        jugador_1: ParticipantePartidaInput,
        jugador_2: ParticipantePartidaInput,
    ) -> PartidaCreada:
        """Genera seed en servidor, prepara inicio en MotorJuego y persiste en SQL."""
        seed = secrets.randbits(63)
        bet_cubes = self._ranked_initial_bet if context == "RANKED" else 0

        todos_ids = list(dict.fromkeys([*jugador_1.card_ids, *jugador_2.card_ids]))
        cartas_map = await self._catalogo.leer_cartas_por_ids(sesion, todos_ids)
        for participante in (jugador_1, jugador_2):
            faltantes = [cid for cid in participante.card_ids if cid not in cartas_map]
            if faltantes:
                raise CatalogoPartidaInvalidoError(
                    f"Faltan cartas válidas del catálogo para el asiento {participante.seat}."
                )

        ubicaciones = await self._catalogo.listar_ubicaciones(sesion)
        entrada_1 = ParticipanteEntrada(
            seat=jugador_1.seat,
            user_id=jugador_1.user_id,
            is_bot=jugador_1.is_bot,
            elo=jugador_1.elo,
            deck_cards=tuple(cartas_map[cid] for cid in jugador_1.card_ids),
        )
        entrada_2 = ParticipanteEntrada(
            seat=jugador_2.seat,
            user_id=jugador_2.user_id,
            is_bot=jugador_2.is_bot,
            elo=jugador_2.elo,
            deck_cards=tuple(cartas_map[cid] for cid in jugador_2.card_ids),
        )

        estado = self._motor.preparar_inicio_partida(
            seed=seed,
            context=context,
            bet_cubes=bet_cubes,
            ubicaciones_candidatas=ubicaciones,
            jugador_1=entrada_1,
            jugador_2=entrada_2,
        )

        decks_snapshots = (
            [cartas_map[cid].to_dict() for cid in jugador_1.card_ids],
            [cartas_map[cid].to_dict() for cid in jugador_2.card_ids],
        )

        return await self._repo.crear_partida_en_sesion(
            sesion,
            match_id=str(uuid4()),
            context=context,
            is_bot_match=is_bot_match,
            bet_cubes=bet_cubes,
            seed=seed,
            turn_duration_seconds=self._turn_duration_seconds,
            estado=estado,
            participantes=(jugador_1, jugador_2),
            decks_snapshots=decks_snapshots,
        )

    async def registrar_version_cache_post_commit(self, partida: PartidaCreada) -> None:
        """Publica state_version en caché estrictamente después del COMMIT SQL."""
        meta = json.dumps({
            "v": partida.state_version,
            "u": list(partida.participant_user_ids),
        })
        await self._cache.set(_clave_version_partida(partida.match_id), meta, _TTL_VISTA_PARTIDA)

    async def obtener_partida_activa(self, user_id: str) -> PartidaActivaResumen | None:
        """Retorna la partida IN_PROGRESS del jugador autenticado."""
        return await self._repo.obtener_partida_activa(user_id)

    async def obtener_vista_partida(
        self,
        user_id: str,
        match_id: str,
        if_none_match: str | None = None,
    ) -> ResultadoVistaPartida:
        """Aplica Cache-Aside versionado + ETag/304 + aislamiento Fog of War."""
        ver_raw = await self._cache.get(_clave_version_partida(match_id))
        if ver_raw is not None:
            try:
                meta = json.loads(ver_raw)
                ver = int(meta["v"])
                participantes = meta["u"]
                if not isinstance(participantes, list):
                    raise ValueError("meta invalido")
            except (ValueError, TypeError, KeyError):
                meta = None
            else:
                if user_id not in participantes:
                    raise PartidaNoEncontradaError("La partida no existe.")
                etag_cache = generar_etag("m", match_id, ver)
                if coincide_if_none_match(if_none_match, etag_cache):
                    return ResultadoVistaPartida(
                        not_modified=True,
                        etag=etag_cache,
                        state_version=ver,
                        payload=None,
                    )
                vista_raw = await self._cache.get(_clave_vista_usuario(match_id, ver, user_id))
                if vista_raw is not None:
                    try:
                        payload_cache = json.loads(vista_raw)
                        if isinstance(payload_cache, dict):
                            return ResultadoVistaPartida(
                                not_modified=False,
                                etag=etag_cache,
                                state_version=ver,
                                payload=payload_cache,
                            )
                    except ValueError:
                        pass

        registro = await self._repo.obtener_partida_para_jugador(user_id, match_id)
        if registro is None:
            raise PartidaNoEncontradaError("La partida no existe.")

        etag = generar_etag("m", match_id, registro.state_version)
        await self._cache.set(
            _clave_version_partida(match_id),
            json.dumps({
                "v": registro.state_version,
                "u": list(registro.participant_user_ids),
            }),
            _TTL_VISTA_PARTIDA,
        )

        if coincide_if_none_match(if_none_match, etag):
            return ResultadoVistaPartida(
                not_modified=True,
                etag=etag,
                state_version=registro.state_version,
                payload=None,
            )

        estado = EstadoPartidaInterno.from_state_dict(registro.state_json)
        vista_motor = self._motor.proyectar_vista_jugador(estado, user_id)
        payload: dict[str, Any] = {
            "match_id": registro.match_id,
            "status": registro.status,
            "is_bot_match": registro.is_bot_match,
            "turn_duration_seconds": registro.turn_duration_seconds,
            "turn_started_at": registro.turn_started_at.isoformat(),
            "turn_ends_at": registro.turn_ends_at.isoformat(),
            "state_version": registro.state_version,
            **vista_motor,
        }
        await self._cache.set(
            _clave_vista_usuario(match_id, registro.state_version, user_id),
            json.dumps(payload),
            _TTL_VISTA_PARTIDA,
        )
        return ResultadoVistaPartida(
            not_modified=False,
            etag=etag,
            state_version=registro.state_version,
            payload=payload,
        )
