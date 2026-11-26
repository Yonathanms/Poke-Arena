"""Adaptadores SQL para Partidas, snapshots de Catálogo y bloqueo de decks en uso."""

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.catalogo import catalogo_module
from src.modules.motor_juego.domain.modelos_partida import (
    CartaSnapshot,
    EstadoPartidaInterno,
    UbicacionSnapshot,
)

from ..domain.partida_model import (
    ParticipantePartidaInput,
    PartidaActivaResumen,
    PartidaConflictoActivaError,
    PartidaCreada,
    PartidaNoDisponibleError,
    RegistroPartidaSQL,
)


def _a_carta_snapshot(fila: dict[str, Any]) -> CartaSnapshot:
    return CartaSnapshot(
        id=str(fila["id"]),
        code=str(fila["code"]),
        name=str(fila["name"]),
        cost=int(fila["cost"]),
        power=int(fila["power"]),
        card_type=str(fila["card_type"]),
        rarity=str(fila["rarity"]),
        ability_code=str(fila["ability_code"]),
        ability_name=str(fila["ability_name"]),
        ability_params=fila.get("ability_params") or {},
    )


def _a_ubicacion_snapshot(fila: dict[str, Any]) -> UbicacionSnapshot:
    return UbicacionSnapshot(
        id=str(fila["id"]),
        nombre=str(fila["nombre"]),
        descripcion=str(fila["descripcion"]),
        card_limit=int(fila["card_limit"]),
        energia_tipo=str(fila["energia_tipo"]),
        energia_valor=int(fila["energia_valor"]),
        efecto_tipo=str(fila["efecto_tipo"]),
        efecto_params=fila.get("efecto_params") or {},
        image_url=str(fila["image_url"]),
        thumbnail_url=str(fila["thumbnail_url"]),
    )


class SqlFuenteCatalogoPartida:
    """Lee snapshots de cartas y ubicaciones mediante la fachada pública de Catálogo."""

    async def leer_cartas_por_ids(
        self, sesion: Any, card_ids: Sequence[str]
    ) -> dict[str, CartaSnapshot]:
        try:
            filas = await catalogo_module.leer_cartas_catalogo_para_partida(sesion, card_ids)
        except SQLAlchemyError:
            raise PartidaNoDisponibleError("No se pudieron leer las cartas del catálogo.") from None
        return {str(fila["id"]): _a_carta_snapshot(fila) for fila in filas}

    async def listar_ubicaciones(self, sesion: Any) -> list[UbicacionSnapshot]:
        try:
            filas = await catalogo_module.listar_ubicaciones_catalogo_para_partida(sesion)
        except SQLAlchemyError:
            raise PartidaNoDisponibleError(
                "No se pudieron leer las ubicaciones del catálogo."
            ) from None
        return [_a_ubicacion_snapshot(fila) for fila in filas]

    async def seleccionar_cartas_bot(self, sesion: Any) -> list[CartaSnapshot]:
        try:
            filas = await catalogo_module.listar_cartas_elegibles_bot(sesion)
        except SQLAlchemyError:
            raise PartidaNoDisponibleError("No se pudieron leer cartas para el Bot.") from None
        return [_a_carta_snapshot(fila) for fila in filas]


class SqlRepositorioPartidas:
    """Persistencia ACID de matches y match_players en PostgreSQL 16."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def crear_partida_en_sesion(
        self,
        sesion: Any,
        *,
        match_id: str,
        context: str,
        is_bot_match: bool,
        bet_cubes: int,
        seed: int,
        turn_duration_seconds: int,
        estado: EstadoPartidaInterno,
        participantes: tuple[ParticipantePartidaInput, ParticipantePartidaInput],
        decks_snapshots: tuple[list[dict[str, Any]], list[dict[str, Any]]],
    ) -> PartidaCreada:
        try:
            fila_match = (
                await sesion.execute(
                    text("""
                        INSERT INTO matches (
                            id, context, status, is_bot_match, bet_cubes, seed,
                            turn_number, turn_duration_seconds,
                            turn_started_at, turn_ends_at,
                            locations_snapshot, deck_orders_snapshot, state_json,
                            state_version, created_at, updated_at
                        )
                        VALUES (
                            :id, :context, 'IN_PROGRESS', :is_bot_match, :bet_cubes, :seed,
                            1, :dur,
                            clock_timestamp(),
                            clock_timestamp() + make_interval(secs => :dur_secs),
                            CAST(:locations_snapshot AS jsonb),
                            CAST(:deck_orders_snapshot AS jsonb),
                            CAST(:state_json AS jsonb),
                            1, clock_timestamp(), clock_timestamp()
                        )
                        RETURNING turn_started_at, turn_ends_at
                    """),
                    {
                        "id": match_id,
                        "context": context,
                        "is_bot_match": is_bot_match,
                        "bet_cubes": bet_cubes,
                        "seed": seed,
                        "dur": int(turn_duration_seconds),
                        "dur_secs": float(turn_duration_seconds),
                        "locations_snapshot": json.dumps(estado.locations_snapshot_dict()),
                        "deck_orders_snapshot": json.dumps(estado.deck_orders_snapshot_dict()),
                        "state_json": json.dumps(estado.to_state_dict()),
                    },
                )
            ).one()

            for participante, deck_snap in zip(participantes, decks_snapshots, strict=True):
                await sesion.execute(
                    text("""
                        INSERT INTO match_players (
                            match_id, user_id, seat, is_bot, deck_id,
                            deck_snapshot, elo_at_start, status
                        )
                        VALUES (
                            :match_id, :user_id, :seat, :is_bot, :deck_id,
                            CAST(:deck_snapshot AS jsonb), :elo_at_start, 'IN_PROGRESS'
                        )
                    """),
                    {
                        "match_id": match_id,
                        "user_id": participante.user_id,
                        "seat": participante.seat,
                        "is_bot": participante.is_bot,
                        "deck_id": participante.deck_id,
                        "deck_snapshot": json.dumps(deck_snap),
                        "elo_at_start": participante.elo,
                    },
                )
        except IntegrityError as exc:
            restriccion = getattr(getattr(exc, "orig", None), "constraint_name", None)
            if restriccion == "uq_match_players_one_active_per_user" or (
                "uq_match_players_one_active_per_user" in str(exc)
            ):
                raise PartidaConflictoActivaError(
                    "Uno de los jugadores ya tiene una partida activa."
                ) from None
            raise PartidaNoDisponibleError("No se pudo registrar la partida.") from None
        except SQLAlchemyError:
            raise PartidaNoDisponibleError("No se pudo registrar la partida.") from None

        participantes_humanos = tuple(
            p.user_id for p in participantes if not p.is_bot and p.user_id is not None
        )
        return PartidaCreada(
            match_id=match_id,
            context=context,
            status="IN_PROGRESS",
            is_bot_match=is_bot_match,
            bet_cubes=bet_cubes,
            turn_number=1,
            turn_duration_seconds=turn_duration_seconds,
            turn_started_at=fila_match[0],
            turn_ends_at=fila_match[1],
            state_version=1,
            participant_user_ids=participantes_humanos,
        )

    async def obtener_partida_activa(self, user_id: str) -> PartidaActivaResumen | None:
        try:
            async with self._factory() as sesion:
                fila = (
                    await sesion.execute(
                        text("""
                            SELECT m.id, m.context, m.status, m.is_bot_match, m.bet_cubes,
                                   m.turn_number, m.turn_duration_seconds,
                                   m.turn_started_at, m.turn_ends_at, m.state_version
                            FROM matches m
                            JOIN match_players mp ON mp.match_id = m.id
                            WHERE mp.user_id = :user_id
                              AND mp.status = 'IN_PROGRESS'
                              AND m.status = 'IN_PROGRESS'
                            ORDER BY m.created_at DESC
                            LIMIT 1
                        """),
                        {"user_id": user_id},
                    )
                ).one_or_none()
        except SQLAlchemyError:
            raise PartidaNoDisponibleError("No se pudo consultar la partida activa.") from None

        if fila is None:
            return None
        return PartidaActivaResumen(
            match_id=str(fila[0]),
            context=str(fila[1]),
            status=str(fila[2]),
            is_bot_match=bool(fila[3]),
            bet_cubes=int(fila[4]),
            turn_number=int(fila[5]),
            turn_duration_seconds=int(fila[6]),
            turn_started_at=fila[7],
            turn_ends_at=fila[8],
            state_version=int(fila[9]),
        )

    async def obtener_partida_para_jugador(
        self, user_id: str, match_id: str
    ) -> RegistroPartidaSQL | None:
        try:
            async with self._factory() as sesion:
                fila = (
                    await sesion.execute(
                        text("""
                            SELECT m.id, m.context, m.status, m.is_bot_match, m.bet_cubes,
                                   m.seed, m.turn_number, m.turn_duration_seconds,
                                   m.turn_started_at, m.turn_ends_at,
                                   m.state_json, m.state_version
                            FROM matches m
                            JOIN match_players mp ON mp.match_id = m.id
                            WHERE m.id = :match_id
                              AND mp.user_id = :user_id
                        """),
                        {"match_id": match_id, "user_id": user_id},
                    )
                ).one_or_none()
                if fila is None:
                    return None
                participantes = (
                    await sesion.scalars(
                        text("""
                            SELECT user_id
                            FROM match_players
                            WHERE match_id = :match_id
                              AND user_id IS NOT NULL
                        """),
                        {"match_id": match_id},
                    )
                ).all()
        except SQLAlchemyError:
            raise PartidaNoDisponibleError("No se pudo consultar la partida.") from None

        return RegistroPartidaSQL(
            match_id=str(fila[0]),
            context=str(fila[1]),
            status=str(fila[2]),
            is_bot_match=bool(fila[3]),
            bet_cubes=int(fila[4]),
            seed=int(fila[5]),
            turn_number=int(fila[6]),
            turn_duration_seconds=int(fila[7]),
            turn_started_at=fila[8],
            turn_ends_at=fila[9],
            state_json=dict(fila[10]),
            state_version=int(fila[11]),
            participant_user_ids=tuple(str(uid) for uid in participantes),
        )

    async def deck_en_partida_activa(self, user_id: str, deck_id: str) -> bool:
        try:
            async with self._factory() as sesion:
                resultado = await sesion.scalar(
                    text("""
                        SELECT EXISTS (
                            SELECT 1
                            FROM match_players
                            WHERE user_id = :user_id
                              AND deck_id = :deck_id
                              AND status = 'IN_PROGRESS'
                        )
                    """),
                    {"user_id": user_id, "deck_id": deck_id},
                )
                return bool(resultado)
        except SQLAlchemyError:
            raise PartidaNoDisponibleError("No se pudo verificar el estado del deck.") from None


class SqlVerificadorDeckEnUso:
    """Implementa VerificadorDeckEnUsoPort para impedir editar/borrar decks en uso."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def esta_en_uso(self, user_id: str, deck_id: str) -> bool:
        try:
            async with self._factory() as sesion:
                en_uso = await sesion.scalar(
                    text("""
                        SELECT (
                            EXISTS (
                                SELECT 1 FROM match_searches
                                WHERE user_id = :user_id
                                  AND deck_id = :deck_id
                                  AND status = 'SEARCHING'
                            )
                            OR EXISTS (
                                SELECT 1 FROM match_players
                                WHERE user_id = :user_id
                                  AND deck_id = :deck_id
                                  AND status = 'IN_PROGRESS'
                            )
                        )
                    """),
                    {"user_id": user_id, "deck_id": deck_id},
                )
                return bool(en_uso)
        except SQLAlchemyError:
            raise PartidaNoDisponibleError("No se pudo verificar si el deck está en uso.") from None
