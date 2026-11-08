"""Adaptador SQL ACID: INSERT locations + outbox_events + idempotency_records en una transacción."""
import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlUbicacionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def verificar_idempotencia(self, key: str) -> dict | None:
        result = await self._db.execute(
            text("SELECT response_body FROM idempotency_records WHERE key = :key"),
            {"key": key},
        )
        row = result.fetchone()
        return row[0] if row else None

    async def guardar(self, datos: dict, outbox_payload: dict, idempotency_key: str) -> dict:
        location_id = uuid.uuid4()

        # Siguiente paso: persistir ubicación, evento outbox e idempotencia en una transacción
        await self._db.execute(
            text("""
                INSERT INTO locations
                    (id, nombre, descripcion, card_limit, energia_tipo, energia_valor,
                     efecto_tipo, efecto_params, url_grande, url_tablero)
                VALUES
                    (:id, :nombre, :descripcion, :card_limit, :energia_tipo, :energia_valor,
                     :efecto_tipo, CAST(:efecto_params AS jsonb), :url_grande, :url_tablero)
            """),
            {
                "id": str(location_id),
                "nombre": datos["nombre"],
                "descripcion": datos["descripcion"],
                "card_limit": datos["card_limit"],
                "energia_tipo": datos["energia_tipo"],
                "energia_valor": datos["energia_valor"],
                "efecto_tipo": datos["efecto_tipo"],
                "efecto_params": json.dumps(datos["efecto_params"]),
                "url_grande": datos["url_grande"],
                "url_tablero": datos["url_tablero"],
            },
        )

        await self._db.execute(
            text("""
                INSERT INTO outbox_events (id, evento, aggregate_id, payload, status, created_at)
                VALUES (:id, 'LocationCreatedEvent', :agg_id, CAST(:payload AS jsonb), 'PENDING', NOW())
            """),
            {
                "id": str(uuid.uuid4()),
                "agg_id": str(location_id),
                "payload": json.dumps(outbox_payload),
            },
        )

        respuesta = {
            "id": str(location_id),
            **{k: datos[k] for k in ("nombre", "descripcion", "card_limit", "energia_tipo",
                                      "energia_valor", "efecto_tipo", "efecto_params",
                                      "url_grande", "url_tablero")},
            "created_at": None,
        }

        await self._db.execute(
            text("""
                INSERT INTO idempotency_records (key, response_status, resource_id, response_body, created_at)
                VALUES (:key, 201, :resource_id, CAST(:response_body AS jsonb), NOW())
            """),
            {
                "key": idempotency_key,
                "resource_id": str(location_id),
                "response_body": json.dumps(respuesta),
            },
        )

        await self._db.commit()
        return respuesta
