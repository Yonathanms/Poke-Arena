"""Adaptador SQL ACID para ubicaciones y lectura autoritativa de reconciliación."""

import json
import uuid
from datetime import datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..ports.ubicaciones_ports import IFuenteUbicacionesSql, IUbicacionRepository

_OPERACION = "POST:/api/v1/content/locations"


def _serializar_fecha(valor: Any) -> str | None:
    if isinstance(valor, datetime):
        return valor.isoformat()
    return str(valor) if valor is not None else None


def _huella_ubicacion(datos: dict[str, Any]) -> str:
    canon = {
        k: datos.get(k)
        for k in (
            "nombre",
            "descripcion",
            "card_limit",
            "energia_tipo",
            "energia_valor",
            "efecto_tipo",
            "efecto_params",
        )
    }
    return sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class SqlUbicacionRepository(IUbicacionRepository):
    """Persiste locations y shared_idempotency_records en una única transacción ACID."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def verificar_idempotencia(self, actor_id: str, key: str) -> dict[str, Any] | None:
        result = await self._db.execute(
            text("""
                SELECT response_body
                FROM shared_idempotency_records
                WHERE actor_id = :actor_id
                  AND operation = :operation
                  AND idempotency_key = :key
            """),
            {"actor_id": actor_id, "operation": _OPERACION, "key": key},
        )
        row = result.fetchone()
        return row[0] if row and row[0] is not None else None

    async def guardar(
        self, actor_id: str, datos: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        location_id = str(uuid.uuid4())

        insert_res = await self._db.execute(
            text("""
                INSERT INTO locations
                    (id, nombre, descripcion, card_limit, energia_tipo, energia_valor,
                     efecto_tipo, efecto_params, url_grande, url_tablero)
                VALUES
                    (:id, :nombre, :descripcion, :card_limit, :energia_tipo, :energia_valor,
                     :efecto_tipo, CAST(:efecto_params AS jsonb), :url_grande, :url_tablero)
                RETURNING created_at
            """),
            {
                "id": location_id,
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
        created_at = insert_res.scalar_one_or_none()

        respuesta: dict[str, Any] = {
            "id": location_id,
            **{
                k: datos[k]
                for k in (
                    "nombre",
                    "descripcion",
                    "card_limit",
                    "energia_tipo",
                    "energia_valor",
                    "efecto_tipo",
                    "efecto_params",
                    "url_grande",
                    "url_tablero",
                )
            },
            "created_at": _serializar_fecha(created_at),
        }

        await self._db.execute(
            text("""
                INSERT INTO shared_idempotency_records
                    (id, actor_id, operation, idempotency_key, endpoint,
                     request_hash, resource_id, response_status, response_body, created_at)
                VALUES
                    (:id, :actor_id, :operation, :key, :endpoint,
                     :request_hash, :resource_id, 201, CAST(:response_body AS jsonb), NOW())
            """),
            {
                "id": str(uuid.uuid4()),
                "actor_id": actor_id,
                "operation": _OPERACION,
                "key": idempotency_key,
                "endpoint": _OPERACION,
                "request_hash": _huella_ubicacion(datos),
                "resource_id": location_id,
                "response_body": json.dumps(respuesta),
            },
        )

        await self._db.commit()
        return respuesta


class SqlFuenteUbicaciones(IFuenteUbicacionesSql):
    """Lee el estado autoritativo de locations en PostgreSQL para reconciliación."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def listar_ubicaciones(self) -> list[dict[str, Any]]:
        async with self._factory() as sesion:
            resultado = await sesion.execute(
                text("""
                    SELECT id, nombre, descripcion, card_limit, energia_tipo, energia_valor,
                           efecto_tipo, efecto_params, url_grande, url_tablero, created_at
                    FROM locations
                    ORDER BY created_at, id
                """)
            )
            filas = resultado.mappings().all()

        return [
            {
                "id": str(fila["id"]),
                "nombre": fila["nombre"],
                "descripcion": fila["descripcion"],
                "card_limit": int(fila["card_limit"]),
                "energia_tipo": fila["energia_tipo"],
                "energia_valor": int(fila["energia_valor"]),
                "efecto_tipo": fila["efecto_tipo"],
                "efecto_params": fila["efecto_params"] or {},
                "url_grande": fila["url_grande"],
                "url_tablero": fila["url_tablero"],
                "created_at": _serializar_fecha(fila["created_at"]),
            }
            for fila in filas
        ]
