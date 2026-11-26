"""Servicio de reconciliación periódica de cartas (PostgreSQL -> MongoDB)."""

import logging
from dataclasses import dataclass
from typing import Any

from ..domain.proyeccion_carta import EventoIncompatible, ProyeccionCarta, ProyeccionTemporal
from ..ports.proyeccion_ports import FuenteCartasSqlPort, ProyeccionCartasPort

logger = logging.getLogger("pokearena.reconciliador")


@dataclass(frozen=True, slots=True)
class ResultadoReconciliacion:
    """Resumen cuantitativo de un ciclo de reconciliación para una entidad."""

    entidad: str
    total_sql: int
    sincronizadas: int
    omitidas: int
    errores: int


def _requiere_sincronizacion(esperado: ProyeccionCarta, actual: dict[str, Any] | None) -> bool:
    """Compara el snapshot autoritativo SQL contra el documento actual en MongoDB."""
    if actual is None:
        return True
    doc_esperado = esperado.documento()
    for clave, valor in doc_esperado.items():
        if clave == "_id":
            continue
        actual_valor = actual.get(clave)
        if actual_valor != valor or (
            isinstance(valor, int)
            and not isinstance(valor, bool)
            and isinstance(actual_valor, bool)
        ):
            return True
    return False


class ReconciliadorCartas:
    """Verifica concordancia entre catalog_cards (SQL) y cards_projection (MongoDB)."""

    def __init__(self, fuente_sql: FuenteCartasSqlPort, destino_mongo: ProyeccionCartasPort) -> None:
        """Inyecta los puertos de lectura SQL y proyección MongoDB."""
        self._fuente_sql = fuente_sql
        self._destino_mongo = destino_mongo
        self._indices_verificados = False

    async def conciliar(self) -> ResultadoReconciliacion:
        """Sincroniza hacia MongoDB únicamente las cartas faltantes o desactualizadas."""
        if not self._indices_verificados:
            await self._destino_mongo.asegurar_indices()
            self._indices_verificados = True

        cartas_sql = await self._fuente_sql.listar_cartas_listas()
        existentes_mongo = await self._destino_mongo.listar_proyecciones()

        sincronizadas = 0
        omitidas = 0
        errores = 0

        for carta in cartas_sql:
            doc_actual = existentes_mongo.get(carta.id)
            if not _requiere_sincronizacion(carta, doc_actual):
                omitidas += 1
                continue
            try:
                await self._destino_mongo.guardar(carta)
                sincronizadas += 1
            except (EventoIncompatible, ProyeccionTemporal) as exc:
                errores += 1
                logger.warning(
                    "reconciliacion_cartas error carta=%s codigo=%s detalle=%s",
                    carta.id,
                    carta.campos.get("code"),
                    exc,
                )

        resultado = ResultadoReconciliacion(
            entidad="cards",
            total_sql=len(cartas_sql),
            sincronizadas=sincronizadas,
            omitidas=omitidas,
            errores=errores,
        )
        logger.info(
            "reconciliacion_cartas total_sql=%d sincronizadas=%d omitidas=%d errores=%d",
            resultado.total_sql,
            resultado.sincronizadas,
            resultado.omitidas,
            resultado.errores,
        )
        return resultado
