"""Pruebas unitarias para el endpoint, validaciones, DTOs y servicio de catálogo de cartas (US 3.1.2)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.main import crear_app
from src.modules.catalogo.gestion_cartas.adapters.sql_inventario_adapter import (
    SqlInventarioJugadorAdapter,
)
from src.modules.catalogo.gestion_cartas.controllers.cartas_dtos import (
    CartaResponseDTO,
    CartaSearchQueryDTO,
    CartaSearchResponseDTO,
    RarezaCarta,
    TipoCarta,
)
from src.modules.catalogo.gestion_cartas.controllers.cartas_validaciones import (
    validar_parametros_busqueda,
)
from src.modules.catalogo.gestion_cartas.services.cartas_service import CartasService


def correr_async(coro):
    """Ejecuta una corrutina en un bucle síncrono dedicado y aislado."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


# ------------------------------------------------------------------------------
# 1. Validaciones descriptivas (RFC 7807)
# ------------------------------------------------------------------------------

def test_tipo_invalido_devuelve_422_con_valores_permitidos():
    with pytest.raises(HTTPException) as exc_info:
        validar_parametros_busqueda(tipo="INVALIDO")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "tipo_invalido"
    assert "Valores permitidos" in exc_info.value.detail["detail"]
    assert "FUE" in exc_info.value.detail["detail"]
    assert "AGU" in exc_info.value.detail["detail"]


def test_costo_fuera_de_rango_devuelve_422_con_valores_permitidos():
    # Costo mayor a 10
    with pytest.raises(HTTPException) as exc_info_max:
        validar_parametros_busqueda(costo=15)

    assert exc_info_max.value.status_code == 422
    assert exc_info_max.value.detail["code"] == "costo_invalido"
    assert "entre 0 y 10" in exc_info_max.value.detail["detail"]

    # Costo negativo
    with pytest.raises(HTTPException) as exc_info_neg:
        validar_parametros_busqueda(costo=-1)

    assert exc_info_neg.value.status_code == 422
    assert exc_info_neg.value.detail["code"] == "costo_invalido"


def test_pagina_invalida_devuelve_error_descriptivo():
    with pytest.raises(HTTPException) as exc_info:
        validar_parametros_busqueda(pagina=0)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "paginacion_invalida"
    assert "mayor o igual a 1" in exc_info.value.detail["detail"]


def test_limite_invalido_devuelve_error_descriptivo():
    with pytest.raises(HTTPException) as exc_info:
        validar_parametros_busqueda(limite=200)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "paginacion_invalida"
    assert "entre 1 y 100" in exc_info.value.detail["detail"]


def test_rareza_invalida_devuelve_422_con_valores_permitidos():
    with pytest.raises(HTTPException) as exc_info:
        validar_parametros_busqueda(rareza="ULTRA_SECRET")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "rareza_invalida"
    assert "Valores permitidos" in exc_info.value.detail["detail"]


def test_filtros_validos_devuelven_tupla_limpia():
    limite, pagina, tipo, rareza = validar_parametros_busqueda(
        pagina=2, limite=20, tipo="fue", costo=4, rareza="comun"
    )
    assert limite == 20
    assert pagina == 2
    assert tipo == TipoCarta.FUE
    assert rareza == RarezaCarta.COMUN


# ------------------------------------------------------------------------------
# 2. DTOs y Esquema Swagger / OpenAPI
# ------------------------------------------------------------------------------

def test_carta_response_dto_incluye_habilidad_y_copias_poseidas():
    dto = CartaResponseDTO(
        id="card-123",
        name="Charizard",
        code="PKA-001",
        type="FUE",
        rarity="LEGENDARIA",
        cost=4,
        power=180,
        hp=220,
        ability_name="Furia Ígnea",
        ability_code="HAB-001",
        owned_copies=2,
        is_owned=True,
    )
    assert dto.ability_name == "Furia Ígnea"
    assert dto.ability_code == "HAB-001"
    assert dto.owned_copies == 2
    assert dto.is_owned is True
    assert dto.thumbnailUrl == "/api/v1/content/cards/card-123/thumbnail"
    assert dto.imageUrl == "/api/v1/content/cards/card-123/image"


def test_carta_search_query_dto_acepta_costo_y_solo_propias():
    query = CartaSearchQueryDTO(
        tipo=TipoCarta.FUE,
        costo=3,
        solo_propias=True,
        user_id="player-xyz-789",
        limite=15,
        pagina=1,
    )
    assert query.costo == 3
    assert query.solo_propias is True
    assert query.user_id == "player-xyz-789"
    assert query.tipo == TipoCarta.FUE


def test_openapi_swagger_registra_parametros_y_rutas_completas():
    app = crear_app()
    schema = app.openapi()
    cards_get = schema["paths"]["/api/v1/content/cards"]["get"]
    param_names = [p["name"] for p in cards_get.get("parameters", [])]

    assert "q" in param_names
    assert "tipo" in param_names
    assert "rareza" in param_names
    assert "costo" in param_names
    assert "solo_propias" in param_names
    assert "limite" in param_names
    assert "pagina" in param_names

    response_props = schema["components"]["schemas"]["CartaResponseDTO"]["properties"]
    assert "ability_name" in response_props
    assert "owned_copies" in response_props
    assert "is_owned" in response_props

    assert "/api/v1/content/cards/{card_id}/thumbnail" in schema["paths"]
    assert "/api/v1/content/cards/{card_id}/image" in schema["paths"]


# ------------------------------------------------------------------------------
# 3. Cruce Catálogo + Inventario (Lógica de Negocio en CartasService)
# ------------------------------------------------------------------------------

def test_cruce_anota_copias_poseidas_correctamente():
    async def _test():
        repo_mock = MagicMock()
        repo_mock.buscar_cartas = AsyncMock(
            return_value=CartaSearchResponseDTO(
                items=[
                    CartaResponseDTO(id="card-1", name="Pikachu", code="PKA-001", type="ELE", cost=2),
                    CartaResponseDTO(id="card-2", name="Bulbasaur", code="PKA-002", type="PLA", cost=1),
                ],
                total=2,
                pagina=1,
                limite=15,
                total_paginas=1,
            )
        )

        inventario_mock = MagicMock()
        inventario_mock.obtener_cantidades_por_usuario = AsyncMock(
            return_value={"card-1": 3}
        )

        srv = CartasService(repository=repo_mock, inventario=inventario_mock)
        params = CartaSearchQueryDTO(user_id="user-123", solo_propias=False)
        resultado = await srv.buscar_cartas(params)

        pikachu = resultado.items[0]
        assert pikachu.id == "card-1"
        assert pikachu.owned_copies == 3
        assert pikachu.is_owned is True

        bulbasaur = resultado.items[1]
        assert bulbasaur.id == "card-2"
        assert bulbasaur.owned_copies == 0
        assert bulbasaur.is_owned is False

    correr_async(_test())


def test_solo_propias_con_inventario_vacio_devuelve_lista_vacia():
    async def _test():
        repo_mock = MagicMock()
        inventario_mock = MagicMock()
        inventario_mock.obtener_cantidades_por_usuario = AsyncMock(return_value={})

        srv = CartasService(repository=repo_mock, inventario=inventario_mock)
        params = CartaSearchQueryDTO(user_id="user-nuevo", solo_propias=True)
        resultado = await srv.buscar_cartas(params)

        assert resultado.total == 0
        assert len(resultado.items) == 0
        assert resultado.total_paginas == 1
        repo_mock.buscar_cartas.assert_not_called()

    correr_async(_test())


def test_solo_propias_con_cartas_inyecta_ids_filtro():
    async def _test():
        repo_mock = MagicMock()
        repo_mock.buscar_cartas = AsyncMock(
            return_value=CartaSearchResponseDTO(
                items=[
                    CartaResponseDTO(id="card-1", name="Pikachu", code="PKA-001", type="ELE", cost=2),
                ],
                total=1,
                pagina=1,
                limite=15,
                total_paginas=1,
            )
        )

        inventario_mock = MagicMock()
        inventario_mock.obtener_cantidades_por_usuario = AsyncMock(
            return_value={"card-1": 2, "card-9": 1}
        )

        srv = CartasService(repository=repo_mock, inventario=inventario_mock)
        params = CartaSearchQueryDTO(user_id="user-123", solo_propias=True)
        resultado = await srv.buscar_cartas(params)

        assert resultado.total == 1
        assert resultado.items[0].owned_copies == 2
        assert resultado.items[0].is_owned is True

        llamada_params = repo_mock.buscar_cartas.call_args[0][0]
        assert set(llamada_params.ids_filtro) == {"card-1", "card-9"}

    correr_async(_test())


def test_obtener_detalle_carta_con_usuario_anota_copias():
    async def _test():
        repo_mock = MagicMock()
        repo_mock.obtener_por_id_o_codigo = AsyncMock(
            return_value=CartaResponseDTO(id="card-1", name="Pikachu", code="PKA-001", cost=2)
        )

        inventario_mock = MagicMock()
        inventario_mock.obtener_cantidades_por_usuario = AsyncMock(
            return_value={"card-1": 5}
        )

        srv = CartasService(repository=repo_mock, inventario=inventario_mock)
        carta = await srv.obtener_detalle_carta("card-1", user_id="user-123")

        assert carta is not None
        assert carta.owned_copies == 5
        assert carta.is_owned is True

    correr_async(_test())


# ------------------------------------------------------------------------------
# 4. Adaptador SQL de Inventario
# ------------------------------------------------------------------------------

def test_obtener_cantidades_sin_usuario_devuelve_diccionario_vacio():
    async def _test():
        adapter = SqlInventarioJugadorAdapter()
        res = await adapter.obtener_cantidades_por_usuario("")
        assert res == {}

    correr_async(_test())


def test_obtener_cantidades_resiliente_ante_fallo_de_sesion():
    async def _test():
        fabrica_rota = MagicMock(side_effect=Exception("Database unavailable"))
        adapter = SqlInventarioJugadorAdapter(session_factory=fabrica_rota)
        res = await adapter.obtener_cantidades_por_usuario("user-cualquiera")
        assert res == {}

    correr_async(_test())
