"""Lógica de negocio para crear ubicaciones: invariantes de dominio + orquestación."""
from fastapi import HTTPException, status


class UbicacionesService:
    def __init__(self, imagen_adapter, sql_repo) -> None:
        self._imagen = imagen_adapter
        self._sql = sql_repo

    async def crear(
        self,
        datos: dict,
        imagen_bytes: bytes,
        content_type: str,
        idempotency_key: str,
    ) -> dict:
        # Siguiente paso: verificar idempotencia preexistente
        existente = await self._sql.verificar_idempotencia(idempotency_key)
        if existente is not None:
            return existente

        # Siguiente paso: validar invariantes de dominio
        self._validar_invariantes(datos)

        # Siguiente paso: procesar imagen aparte
        url_grande, url_tablero = await self._imagen.procesar(imagen_bytes, content_type)

        datos_completos = {**datos, "url_grande": url_grande, "url_tablero": url_tablero}

        # Siguiente paso: persistir en PostgreSQL y registrar en outbox
        return await self._sql.guardar(datos_completos, datos_completos.copy(), idempotency_key)

    # Validando condiciones invariantes (de negocio)
    def _validar_invariantes(self, datos: dict) -> None:
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

    def _validar_efecto(self, efecto_tipo: str, params: dict) -> None:
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
