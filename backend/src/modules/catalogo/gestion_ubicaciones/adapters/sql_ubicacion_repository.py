"""Adaptador SQL ACID para ubicaciones y lectura autoritativa de reconciliación."""

import json
import uuid
from datetime import datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..ports.ubicaciones_ports import (
    ErrorImagenUbicacion,
    IFuenteUbicacionesSql,
    IUbicacionRepository,
)

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
    """Persiste locations y shared_idempotency_records en transacciones ACID cortas."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def verificar_idempotencia(self, actor_id: str, key: str) -> dict[str, Any] | None:
        async with self._factory() as sesion:
            result = await sesion.execute(
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

        async with self._factory() as sesion, sesion.begin():
            insert_res = await sesion.execute(
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

            await sesion.execute(
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

        return respuesta


def _normalizar_referencia_gridfs(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    if not limpio:
        return None
    if limpio.startswith("gridfs:"):
        return limpio
    if len(limpio) == 24 and all(c in "0123456789abcdefABCDEF" for c in limpio):
        return f"gridfs:{limpio}"
    return None


class SqlFuenteUbicaciones(IFuenteUbicacionesSql):
    """Lee el estado autoritativo de locations en PostgreSQL para reconciliación."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def obtener_referencia_imagen(self, location_id: str, variante: str) -> str | None:
        try:
            async with self._factory() as sesion:
                fila = (
                    await sesion.execute(
                        text("""
                            SELECT url_grande, url_tablero, imagen_grande_id, imagen_thumb_id
                            FROM locations
                            WHERE id = :id
                        """),
                        {"id": location_id},
                    )
                ).mappings().one_or_none()
        except SQLAlchemyError:
            raise ErrorImagenUbicacion("No se pudo consultar la imagen de ubicación.") from None

        if fila is None:
            return None

        if variante == "thumbnail":
            candidatos = (fila.get("url_tablero"), fila.get("imagen_thumb_id"))
        else:
            candidatos = (fila.get("url_grande"), fila.get("imagen_grande_id"))

        for candidato in candidatos:
            normalizada = _normalizar_referencia_gridfs(candidato)
            if normalizada is not None:
                return normalizada
        return None

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
