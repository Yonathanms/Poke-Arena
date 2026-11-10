"""Adaptador SQL para creación y consulta de decks del jugador."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.deck_model import (
    Deck,
    DeckCartasNoPertenecen,
    DeckEnCurso,
    DeckNoEncontrado,
    DeckNombreOcupado,
    DeckResumen,
)

_OPERACION = "POST /player/decks"


class SqlRepositorioDecks:

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def crear_deck(
        self,
        user_id: str,
        name: str,
        card_ids: list[str],
        idempotency_key: str,
    ) -> Deck:
        """Transacción atómica: idempotencia → ownership → INSERT deck + cartas."""
        from src.database.postgresql.connection import transactional_session

        try:
            async with transactional_session(self._factory) as sesion:
                return await self._ejecutar_creacion(
                    sesion, user_id, name, card_ids, idempotency_key
                )
        except (DeckCartasNoPertenecen, DeckNombreOcupado, DeckEnCurso):
            raise
        except SQLAlchemyError:
            raise SQLAlchemyError("No se pudo confirmar el deck.") from None

    async def _ejecutar_creacion(
        self,
        sesion: AsyncSession,
        user_id: str,
        name: str,
        card_ids: list[str],
        idempotency_key: str,
    ) -> Deck:
        # 1. Idempotencia: replay si la clave ya fue procesada
        existente = (await sesion.execute(
            text("""
                SELECT resource_id, response_body
                FROM shared_idempotency_records
                WHERE actor_id = :actor
                  AND operation = :operacion
                  AND idempotency_key = :clave
                FOR UPDATE
            """),
            {"actor": user_id, "operacion": _OPERACION, "clave": idempotency_key},
        )).one_or_none()

        if existente is not None:
            resource_id, response_body = existente
            if response_body is None:
                raise DeckEnCurso()
            return await self._leer_deck(sesion, resource_id, user_id)

        # 2. Reservar clave de idempotencia
        ahora = datetime.now(timezone.utc)
        idem_id = str(uuid4())
        deck_id = str(uuid4())

        try:
            await sesion.execute(
                text("""
                    INSERT INTO shared_idempotency_records
                        (id, actor_id, operation, idempotency_key, endpoint,
                         resource_id, request_hash, created_at)
                    VALUES
                        (:id, :actor, :operacion, :clave, :endpoint,
                         :deck_id, :hash, :ahora)
                """),
                {
                    "id": idem_id,
                    "actor": user_id,
                    "operacion": _OPERACION,
                    "clave": idempotency_key,
                    "endpoint": _OPERACION,
                    "deck_id": deck_id,
                    "hash": idempotency_key,
                    "ahora": ahora,
                },
            )
        except IntegrityError:
            raise DeckEnCurso() from None

        # 3. Verificar ownership de las cartas
        await self._validar_ownership(sesion, user_id, card_ids)

        # 4. Insertar el deck
        try:
            await sesion.execute(
                text("""
                    INSERT INTO player_decks (id, user_id, name, created_at)
                    VALUES (:id, :user_id, :name, :ahora)
                """),
                {"id": deck_id, "user_id": user_id, "name": name, "ahora": ahora},
            )
        except IntegrityError:
            raise DeckNombreOcupado(nombre=name) from None

        # 5. Insertar cartas del deck
        await sesion.execute(
            text("INSERT INTO player_deck_cards (deck_id, card_id) VALUES (:deck, :carta)"),
            [{"deck": deck_id, "carta": cid} for cid in card_ids],
        )

        # 6. Marcar idempotencia completada
        await sesion.execute(
            text("""
                UPDATE shared_idempotency_records
                SET response_status = 201,
                    response_body = CAST(:body AS jsonb)
                WHERE id = :id
            """),
            {
                "id": idem_id,
                "body": json.dumps({
                    "id": deck_id,
                    "name": name,
                    "card_count": len(card_ids),
                    "created_at": ahora.isoformat(),
                }),
            },
        )

        return Deck(
            id=deck_id,
            user_id=user_id,
            name=name,
            card_ids=frozenset(card_ids),
            created_at=ahora,
        )

    async def _validar_ownership(
        self, sesion: AsyncSession, user_id: str, card_ids: list[str]
    ) -> None:
        filas = await sesion.execute(
            text("""
                SELECT card_id FROM player_cards
                WHERE user_id = :user AND card_id = ANY(:cartas)
            """),
            {"user": user_id, "cartas": card_ids},
        )
        poseidas = {fila[0] for fila in filas}
        faltantes = [cid for cid in card_ids if cid not in poseidas]
        if faltantes:
            raise DeckCartasNoPertenecen(faltantes=faltantes)

    async def _leer_deck(self, sesion: AsyncSession, deck_id: str, user_id: str) -> Deck:
        fila = (await sesion.execute(
            text("""
                SELECT id, user_id, name, created_at FROM player_decks
                WHERE id = :id AND user_id = :user
            """),
            {"id": deck_id, "user": user_id},
        )).one()
        cartas = await sesion.scalars(
            text("SELECT card_id FROM player_deck_cards WHERE deck_id = :id"),
            {"id": deck_id},
        )
        return Deck(
            id=fila[0],
            user_id=fila[1],
            name=fila[2],
            card_ids=frozenset(cartas.all()),
            created_at=fila[3],
        )

    async def listar_decks(self, user_id: str) -> list[DeckResumen]:
        from src.database.postgresql.connection import AsyncSessionLocal

        async with AsyncSessionLocal() as sesion:
            filas = await sesion.execute(
                text("""
                    SELECT d.id, d.name, COUNT(dc.card_id) AS card_count, d.created_at
                    FROM player_decks d
                    LEFT JOIN player_deck_cards dc ON dc.deck_id = d.id
                    WHERE d.user_id = :user
                    GROUP BY d.id
                    ORDER BY d.created_at DESC
                """),
                {"user": user_id},
            )
            return [
                DeckResumen(id=f[0], name=f[1], card_count=f[2], created_at=f[3])
                for f in filas
            ]

    async def contar_decks(self, user_id: str) -> int:
        from src.database.postgresql.connection import AsyncSessionLocal

        async with AsyncSessionLocal() as sesion:
            resultado = await sesion.scalar(
                text("SELECT COUNT(*) FROM player_decks WHERE user_id = :user"),
                {"user": user_id},
            )
            return int(resultado or 0)

    async def obtener_deck(self, user_id: str, deck_id: str) -> Deck:
        from src.database.postgresql.connection import AsyncSessionLocal

        async with AsyncSessionLocal() as sesion:
            fila = (await sesion.execute(
                text("""
                    SELECT id, user_id, name, created_at FROM player_decks
                    WHERE id = :id AND user_id = :user
                """),
                {"id": deck_id, "user": user_id},
            )).one_or_none()
            if fila is None:
                raise DeckNoEncontrado()
            cartas = await sesion.scalars(
                text("SELECT card_id FROM player_deck_cards WHERE deck_id = :id"),
                {"id": deck_id},
            )
            return Deck(
                id=fila[0], user_id=fila[1], name=fila[2],
                card_ids=frozenset(cartas.all()), created_at=fila[3],
            )

    async def actualizar_deck(
        self, user_id: str, deck_id: str, name: str, card_ids: list[str]
    ) -> Deck:
        from src.database.postgresql.connection import transactional_session

        try:
            async with transactional_session(self._factory) as sesion:
                fila = (await sesion.execute(
                    text("SELECT id FROM player_decks WHERE id = :id AND user_id = :user FOR UPDATE"),
                    {"id": deck_id, "user": user_id},
                )).one_or_none()
                if fila is None:
                    raise DeckNoEncontrado()

                await self._validar_ownership(sesion, user_id, card_ids)

                try:
                    await sesion.execute(
                        text("UPDATE player_decks SET name = :name WHERE id = :id"),
                        {"name": name, "id": deck_id},
                    )
                except IntegrityError:
                    raise DeckNombreOcupado(nombre=name) from None

                await sesion.execute(
                    text("DELETE FROM player_deck_cards WHERE deck_id = :id"),
                    {"id": deck_id},
                )
                await sesion.execute(
                    text("INSERT INTO player_deck_cards (deck_id, card_id) VALUES (:deck, :carta)"),
                    [{"deck": deck_id, "carta": cid} for cid in card_ids],
                )
                ahora = (await sesion.execute(
                    text("SELECT created_at FROM player_decks WHERE id = :id"),
                    {"id": deck_id},
                )).scalar_one()
                return Deck(
                    id=deck_id, user_id=user_id, name=name,
                    card_ids=frozenset(card_ids), created_at=ahora,
                )
        except (DeckCartasNoPertenecen, DeckNombreOcupado, DeckNoEncontrado):
            raise
        except SQLAlchemyError:
            raise SQLAlchemyError("No se pudo actualizar el deck.") from None

    async def eliminar_deck(self, user_id: str, deck_id: str) -> None:
        from src.database.postgresql.connection import transactional_session

        async with transactional_session(self._factory) as sesion:
            resultado = await sesion.execute(
                text("DELETE FROM player_decks WHERE id = :id AND user_id = :user"),
                {"id": deck_id, "user": user_id},
            )
            if resultado.rowcount == 0:
                raise DeckNoEncontrado()
