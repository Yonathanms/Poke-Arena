"""Lógica de negocio de ubicaciones: invariantes, escritura directa SQL->Mongo y reconciliación."""

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from ..ports.ubicaciones_ports import (
    IFuenteUbicacionesSql,
    IProcesadorImagenUbicacion,
    IProyeccionUbicacionRepository,
    IUbicacionRepository,
)

logger = logging.getLogger("pokearena.catalogo.ubicaciones")


class UbicacionesService:
    def __init__(
        self,
        imagen_adapter: IProcesadorImagenUbicacion,
        sql_repo: IUbicacionRepository,
        mongo_repo: IProyeccionUbicacionRepository | None = None,
    ) -> None:
        self._imagen = imagen_adapter
        self._sql = sql_repo
        self._mongo = mongo_repo

    async def crear(
        self,
        datos: dict[str, Any],
        imagen_bytes: bytes,
        content_type: str,
        idempotency_key: str,
        actor_id: str = "admin",
    ) -> dict[str, Any]:
        # 1. Verificar idempotencia preexistente
        existente = await self._sql.verificar_idempotencia(actor_id, idempotency_key)
        if existente is not None:
            return existente

        # 2. Validar invariantes de dominio
        self._validar_invariantes(datos)

        # 3. Procesar imagen y subir a GridFS
        url_grande, url_tablero = await self._imagen.procesar(imagen_bytes, content_type)
        datos_completos = {**datos, "url_grande": url_grande, "url_tablero": url_tablero}

        # 4. Persistir en PostgreSQL con transacción ACID
        respuesta = await self._sql.guardar(actor_id, datos_completos, idempotency_key)

        # 5. Tras el commit ACID en PostgreSQL, proyectar directamente en MongoDB (best-effort)
        if self._mongo is not None:
            try:
                await self._mongo.sincronizar(respuesta)
            except Exception as exc:
                logger.warning(
                    "Proyección directa en MongoDB falló para ubicación %s; "
                    "quedará pendiente para el reconciliador periódico: %s",
                    respuesta.get("id"),
                    exc,
                )

        return respuesta

    def _validar_invariantes(self, datos: dict[str, Any]) -> None:
        if not (0 <= datos["card_limit"] <= 5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="card_limit debe estar entre 0 y 5.",
            )

        energia_tipo = datos["energia_tipo"]
        energia_valor = datos["energia_valor"]
        if energia_tipo == "FIJA":
            if not (0 <= energia_valor <= 3):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Para modo FIJA, energia_valor debe estar entre 0 y 3.",
                )
        elif energia_tipo == "POR_CARTAS":
            if not (0 <= energia_valor <= 2):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Para modo POR_CARTAS, energia_valor debe estar entre 0 y 2.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"energia_tipo '{energia_tipo}' no es válido. Use FIJA o POR_CARTAS.",
            )

        self._validar_efecto(datos["efecto_tipo"], datos.get("efecto_params", {}))

    def _validar_efecto(self, efecto_tipo: str, params: dict[str, Any]) -> None:
        _TIPOS_POKEMON = {"FUE", "AGU", "PLA", "ELE", "PSI", "LUC"}

        if efecto_tipo == "BONIFICACION_POR_TIPO":
            if params.get("tipo") not in _TIPOS_POKEMON:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="BONIFICACION_POR_TIPO requiere 'tipo' válido (FUE, AGU, PLA, ELE, PSI, LUC).",
                )
            if not (-5 <= params.get("cantidad", 999) <= 5):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="BONIFICACION_POR_TIPO requiere 'cantidad' entre -5 y 5.",
                )

        elif efecto_tipo == "MODIFICADOR_COSTO":
            if not (-5 <= params.get("cantidad", 999) <= 5):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="MODIFICADOR_COSTO requiere 'cantidad' entre -5 y 5.",
                )
            tipo_opt = params.get("tipo")
            if tipo_opt is not None and tipo_opt not in _TIPOS_POKEMON:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="MODIFICADOR_COSTO: 'tipo' opcional debe ser FUE, AGU, PLA, ELE, PSI o LUC.",
                )

        elif efecto_tipo == "RESTRICCION_TURNO":
            turnos = params.get("turnos", [])
            if not turnos or not all(isinstance(t, int) and t > 0 for t in turnos):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="RESTRICCION_TURNO requiere 'turnos': lista de enteros positivos.",
                )

        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"efecto_tipo '{efecto_tipo}' no es válido.",
            )


@dataclass(frozen=True, slots=True)
class ResultadoReconciliacionUbicaciones:
    """Resumen cuantitativo de un ciclo de reconciliación de ubicaciones."""

    entidad: str
    total_sql: int
    sincronizadas: int
    omitidas: int
    errores: int


def _ubicacion_requiere_sincronizacion(
    esperada: dict[str, Any], actual: dict[str, Any] | None
) -> bool:
    """Compara el registro autoritativo SQL contra el documento actual en MongoDB."""
    if actual is None:
        return True
    for clave, valor in esperada.items():
        if actual.get(clave) != valor:
            return True
    return False


class ReconciliadorUbicaciones:
    """Verifica concordancia entre locations (SQL) y locations_catalog (MongoDB)."""

    def __init__(
        self,
        fuente_sql: IFuenteUbicacionesSql,
        destino_mongo: IProyeccionUbicacionRepository,
    ) -> None:
        self._fuente_sql = fuente_sql
        self._destino_mongo = destino_mongo

    async def conciliar(self) -> ResultadoReconciliacionUbicaciones:
        """Sincroniza hacia MongoDB únicamente las ubicaciones faltantes o desactualizadas."""
        ubicaciones_sql = await self._fuente_sql.listar_ubicaciones()
        existentes_mongo = await self._destino_mongo.listar_proyecciones()

        sincronizadas = 0
        omitidas = 0
        errores = 0

        for ubicacion in ubicaciones_sql:
            doc_actual = existentes_mongo.get(ubicacion["id"])
            if not _ubicacion_requiere_sincronizacion(ubicacion, doc_actual):
                omitidas += 1
                continue
            try:
                await self._destino_mongo.sincronizar(ubicacion)
                sincronizadas += 1
            except Exception as exc:
                errores += 1
                logger.warning(
                    "reconciliacion_ubicaciones error ubicacion=%s detalle=%s",
                    ubicacion["id"],
                    exc,
                )

        resultado = ResultadoReconciliacionUbicaciones(
            entidad="locations",
            total_sql=len(ubicaciones_sql),
            sincronizadas=sincronizadas,
            omitidas=omitidas,
            errores=errores,
        )
        logger.info(
            "reconciliacion_ubicaciones total_sql=%d sincronizadas=%d omitidas=%d errores=%d",
            resultado.total_sql,
            resultado.sincronizadas,
            resultado.omitidas,
            resultado.errores,
        )
        return resultado
