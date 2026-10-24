"""Servicio genérico de Idempotencia para endpoints de escritura (RNF-INT-01, DA-01)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.infrastructure.models import IdempotencyRecordModel


class IdempotencyService:
    """
    Gestiona el almacenamiento y recuperación de respuestas cacheadas por Idempotency-Key.
    Garantiza que reintentos de red no dupliquen transacciones en la base de datos.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_recorded_response(
        self, idempotency_key: str, endpoint: str
    ) -> dict[str, Any] | None:
        """Retorna la respuesta almacenada si la llave ya fue procesada."""
        stmt = select(IdempotencyRecordModel).where(
            IdempotencyRecordModel.idempotency_key == idempotency_key,
            IdempotencyRecordModel.endpoint == endpoint,
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            return {
                "status_code": record.response_status,
                "body": record.response_body,
            }
        return None

    async def record_response(
        self,
        idempotency_key: str,
        endpoint: str,
        response_status: int,
        response_body: dict[str, Any],
    ) -> None:
        """Almacena la respuesta generada para responder a solicitudes idénticas futuras."""
        record = IdempotencyRecordModel(
            idempotency_key=idempotency_key,
            endpoint=endpoint,
            response_status=response_status,
            response_body=response_body,
        )
        self.db.add(record)
        await self.db.flush()
