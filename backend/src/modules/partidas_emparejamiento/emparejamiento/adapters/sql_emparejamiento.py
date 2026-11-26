"""Adaptador SQL ACID para Emparejamiento (PostgreSQL 16 + locks deterministas)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.postgresql.connection import transactional_session
from src.modules.motor_juego.domain.maquina_estados import (
    MAQUINA_ESTADOS_BUSQUEDA,
    EstadoBusqueda,
    EventoBusqueda,
)

from ..domain.emparejamiento_model import (
    BusquedaActivaDuplicadaError,
    BusquedaPartida,
    DeckInvalidoBusquedaError,
    DeckNoEncontradoBusquedaError,
    EmparejamientoNoDisponibleError,
    PerfilBusqueda,
)

_COLS_BUSQUEDA = """
    id, user_id, deck_id, context, elo_snapshot, status, match_id,
    state_version, created_at, last_seen_at,
    GREATEST(0.0, EXTRACT(EPOCH FROM (clock_timestamp() - created_at))) AS elapsed_seconds,
    GREATEST(0.0, EXTRACT(EPOCH FROM (clock_timestamp() - last_seen_at))) AS inactive_seconds
"""


def _a_busqueda(fila: Any) -> BusquedaPartida:
    return BusquedaPartida(
        id=str(fila[0]),
        user_id=str(fila[1]),
        deck_id=str(fila[2]) if fila[2] is not None else None,
        context=str(fila[3]),
        elo_snapshot=int(fila[4]),
        status=str(fila[5]),
        match_id=str(fila[6]) if fila[6] is not None else None,
        state_version=int(fila[7]),
        created_at=fila[8],
        last_seen_at=fila[9],
        elapsed_seconds=float(fila[10] or 0.0),
        inactive_seconds=float(fila[11] or 0.0),
    )


class SqlRepositorioEmparejamiento:
    """Gestiona match_searches, validación de decks y perfiles en PostgreSQL."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    @asynccontextmanager
    async def abrir_transaccion(self) -> AsyncIterator[AsyncSession]:
        async with transactional_session(self._factory) as sesion:
            yield sesion

    @asynccontextmanager
    async def abrir_savepoint(self, sesion: Any) -> AsyncIterator[None]:
        async with sesion.begin_nested():
            yield

    async def expirar_busquedas_vencidas_usuario(
        self, sesion: Any, user_id: str, heartbeat_timeout_seconds: int
    ) -> list[BusquedaPartida]:
        try:
            filas = (
                await sesion.execute(
                    text(f"""
                        SELECT {_COLS_BUSQUEDA}
                        FROM match_searches
                        WHERE user_id = :user_id
                          AND status = 'SEARCHING'
                          AND last_seen_at < clock_timestamp() - make_interval(secs => :timeout)
                        FOR UPDATE
                    """),
                    {"user_id": user_id, "timeout": heartbeat_timeout_seconds},
                )
            ).all()
            if not filas:
                return []
            expiradas: list[BusquedaPartida] = []
            for fila in filas:
                b = _a_busqueda(fila)
                nuevo_estado = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                    EstadoBusqueda(b.status), EventoBusqueda.EXPIRAR
                ).value
                expiradas.append(
                    await self.actualizar_estado_busqueda(
                        sesion, search_id=b.id, nuevo_estado=nuevo_estado
                    )
                )
            return expiradas
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al expirar búsquedas vencidas.") from None

    async def expirar_busquedas_vencidas_contexto(
        self, sesion: Any, context: str, heartbeat_timeout_seconds: int
    ) -> list[BusquedaPartida]:
        try:
            filas = (
                await sesion.execute(
                    text(f"""
                        SELECT {_COLS_BUSQUEDA}
                        FROM match_searches
                        WHERE context = :context
                          AND status = 'SEARCHING'
                          AND last_seen_at < clock_timestamp() - make_interval(secs => :timeout)
                        FOR UPDATE SKIP LOCKED
                        LIMIT 50
                    """),
                    {"context": context, "timeout": heartbeat_timeout_seconds},
                )
            ).all()
            if not filas:
                return []
            expiradas: list[BusquedaPartida] = []
            for fila in filas:
                b = _a_busqueda(fila)
                nuevo_estado = MAQUINA_ESTADOS_BUSQUEDA.transicionar(
                    EstadoBusqueda(b.status), EventoBusqueda.EXPIRAR
                ).value
                expiradas.append(
                    await self.actualizar_estado_busqueda(
                        sesion, search_id=b.id, nuevo_estado=nuevo_estado
                    )
                )
            return expiradas
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al limpiar cola de búsqueda.") from None

    async def obtener_partida_activa_en_sesion(self, sesion: Any, user_id: str) -> str | None:
        try:
            match_id = await sesion.scalar(
                text("""
                    SELECT mp.match_id
                    FROM match_players mp
                    JOIN matches m ON m.id = mp.match_id
                    WHERE mp.user_id = :user_id
                      AND mp.status = 'IN_PROGRESS'
                      AND m.status = 'IN_PROGRESS'
                    LIMIT 1
                """),
                {"user_id": user_id},
            )
            return str(match_id) if match_id is not None else None
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al verificar partida activa.") from None

    async def obtener_busqueda_activa_usuario_for_update(
        self, sesion: Any, user_id: str
    ) -> BusquedaPartida | None:
        try:
            fila = (
                await sesion.execute(
                    text(f"""
                        SELECT {_COLS_BUSQUEDA}
                        FROM match_searches
                        WHERE user_id = :user_id
                          AND status = 'SEARCHING'
                        FOR UPDATE
                    """),
                    {"user_id": user_id},
                )
            ).one_or_none()
            return _a_busqueda(fila) if fila is not None else None
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al consultar búsqueda abierta.") from None

    async def obtener_busqueda_por_id_for_update(
        self, sesion: Any, user_id: str, search_id: str
    ) -> BusquedaPartida | None:
        try:
            fila = (
                await sesion.execute(
                    text(f"""
                        SELECT {_COLS_BUSQUEDA}
                        FROM match_searches
                        WHERE id = :search_id
                          AND user_id = :user_id
                        FOR UPDATE
                    """),
                    {"search_id": search_id, "user_id": user_id},
                )
            ).one_or_none()
            return _a_busqueda(fila) if fila is not None else None
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al consultar la búsqueda.") from None

    async def validar_y_leer_deck_para_busqueda(
        self, sesion: Any, user_id: str, deck_id: str
    ) -> tuple[str, ...]:
        try:
            existe = await sesion.scalar(
                text("SELECT id FROM player_decks WHERE id = :deck_id AND user_id = :user_id"),
                {"deck_id": deck_id, "user_id": user_id},
            )
            if existe is None:
                raise DeckNoEncontradoBusquedaError(
                    "El deck indicado no existe o no pertenece a tu cuenta."
                )

            card_ids = list(
                (
                    await sesion.scalars(
                        text("""
                            SELECT card_id
                            FROM player_deck_cards
                            WHERE deck_id = :deck_id
                            ORDER BY card_id
                        """),
                        {"deck_id": deck_id},
                    )
                ).all()
            )
            if len(card_ids) != 12 or len(set(card_ids)) != 12:
                raise DeckInvalidoBusquedaError(
                    f"El deck debe tener exactamente 12 cartas distintas (tiene {len(card_ids)})."
                )

            poseidas = set(
                (
                    await sesion.scalars(
                        text("""
                            SELECT card_id
                            FROM player_cards
                            WHERE user_id = :user_id
                              AND card_id = ANY(:card_ids)
                        """),
                        {"user_id": user_id, "card_ids": card_ids},
                    )
                ).all()
            )
            faltantes = [cid for cid in card_ids if cid not in poseidas]
            if faltantes:
                raise DeckInvalidoBusquedaError(
                    f"El deck contiene cartas que ya no están en tu colección: {faltantes}."
                )
            return tuple(str(cid) for cid in card_ids)
        except (DeckNoEncontradoBusquedaError, DeckInvalidoBusquedaError):
            raise
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al validar el deck.") from None

    async def leer_perfil_jugador(self, sesion: Any, user_id: str) -> PerfilBusqueda:
        try:
            fila = (
                await sesion.execute(
                    text("""
                        SELECT elo, cubes
                        FROM player_profiles
                        WHERE user_id = :user_id
                    """),
                    {"user_id": user_id},
                )
            ).one_or_none()
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al leer el perfil del jugador.") from None

        if fila is None:
            raise EmparejamientoNoDisponibleError("El perfil del jugador no está disponible.")
        return PerfilBusqueda(elo=int(fila[0]), cubes=int(fila[1]))

    async def insertar_busqueda(
        self,
        sesion: Any,
        *,
        search_id: str,
        user_id: str,
        deck_id: str,
        context: str,
        elo_snapshot: int,
    ) -> BusquedaPartida:
        try:
            fila = (
                await sesion.execute(
                    text(f"""
                        INSERT INTO match_searches (
                            id, user_id, deck_id, context, elo_snapshot,
                            status, match_id, state_version,
                            created_at, last_seen_at, updated_at
                        )
                        VALUES (
                            :id, :user_id, :deck_id, :context, :elo_snapshot,
                            'SEARCHING', NULL, 1,
                            clock_timestamp(), clock_timestamp(), clock_timestamp()
                        )
                        RETURNING {_COLS_BUSQUEDA}
                    """),
                    {
                        "id": search_id,
                        "user_id": user_id,
                        "deck_id": deck_id,
                        "context": context,
                        "elo_snapshot": elo_snapshot,
                    },
                )
            ).one()
            return _a_busqueda(fila)
        except IntegrityError as exc:
            restriccion = getattr(getattr(exc, "orig", None), "constraint_name", None)
            if restriccion == "uq_match_searches_one_active_per_user" or (
                "uq_match_searches_one_active_per_user" in str(exc)
            ):
                raise BusquedaActivaDuplicadaError() from None
            raise EmparejamientoNoDisponibleError("No se pudo registrar la búsqueda.") from None
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("No se pudo registrar la búsqueda.") from None

    async def refrescar_heartbeat(self, sesion: Any, search_id: str) -> BusquedaPartida:
        try:
            fila = (
                await sesion.execute(
                    text(f"""
                        UPDATE match_searches
                        SET last_seen_at = clock_timestamp(),
                            updated_at = clock_timestamp()
                        WHERE id = :search_id
                        RETURNING {_COLS_BUSQUEDA}
                    """),
                    {"search_id": search_id},
                )
            ).one()
            return _a_busqueda(fila)
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al refrescar heartbeat.") from None

    async def listar_candidatos_skip_locked(
        self,
        sesion: Any,
        *,
        context: str,
        excluir_user_id: str,
        heartbeat_timeout_seconds: int,
        limite: int = 20,
    ) -> list[BusquedaPartida]:
        try:
            filas = (
                await sesion.execute(
                    text(f"""
                        SELECT {_COLS_BUSQUEDA}
                        FROM match_searches
                        WHERE context = :context
                          AND status = 'SEARCHING'
                          AND user_id <> :excluir_user_id
                          AND last_seen_at >= clock_timestamp() - make_interval(secs => :timeout)
                        ORDER BY created_at ASC, id ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT :limite
                    """),
                    {
                        "context": context,
                        "excluir_user_id": excluir_user_id,
                        "timeout": heartbeat_timeout_seconds,
                        "limite": limite,
                    },
                )
            ).all()
            return [_a_busqueda(fila) for fila in filas]
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al buscar rivales compatibles.") from None

    async def bloquear_par_ordenado_por_usuario(
        self, sesion: Any, id_a: str, id_b: str
    ) -> list[BusquedaPartida]:
        try:
            filas = (
                await sesion.execute(
                    text(f"""
                        SELECT {_COLS_BUSQUEDA}
                        FROM match_searches
                        WHERE id = ANY(:ids)
                        ORDER BY user_id ASC
                        FOR UPDATE
                    """),
                    {"ids": [id_a, id_b]},
                )
            ).all()
            return [_a_busqueda(fila) for fila in filas]
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al bloquear búsquedas.") from None

    async def actualizar_estado_busqueda(
        self,
        sesion: Any,
        *,
        search_id: str,
        nuevo_estado: str,
        match_id: str | None = None,
    ) -> BusquedaPartida:
        try:
            fila = (
                await sesion.execute(
                    text(f"""
                        UPDATE match_searches
                        SET status = :nuevo_estado,
                            match_id = COALESCE(:match_id, match_id),
                            state_version = state_version + 1,
                            updated_at = clock_timestamp()
                        WHERE id = :search_id
                        RETURNING {_COLS_BUSQUEDA}
                    """),
                    {
                        "search_id": search_id,
                        "nuevo_estado": nuevo_estado,
                        "match_id": match_id,
                    },
                )
            ).one()
            return _a_busqueda(fila)
        except SQLAlchemyError:
            raise EmparejamientoNoDisponibleError("Error al actualizar búsqueda.") from None
