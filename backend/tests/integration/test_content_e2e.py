import io
import json

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import text

from src.main import app
from src.shared.infrastructure.database import Base, read_engine, write_engine
from src.shared.infrastructure.mongo import get_mongo_db


def generate_image(width: int, height: int, color: str = "blue") -> io.BytesIO:
    """Helper para generar imágenes en memoria con dimensiones exactas."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


@pytest.mark.asyncio
async def test_sprint_1_content_lifecycle_e2e() -> None:
    """
    Prueba E2E completa del ciclo de vida del módulo Content (Sprint 1):
    1. Health check de persistencia políglota (PostgreSQL Master, Réplica y MongoDB).
    2. Crear carta válida con imagen 5:7 y registrarla en PostgreSQL + MongoDB.
    3. Buscar la carta en la proyección de MongoDB con filtros.
    4. Validar rechazo de regla de negocio (costo fuera de rango 1..6) en formato RFC 7807.
    5. Validar rechazo de proporción de imagen de carta inválida (1:1 en vez de 5:7).
    6. Crear ubicación de juego válida con imagen 4:3 y registrarla en PostgreSQL.
    7. Listar ubicaciones disponibles desde la réplica de lectura.
    """
    # 0. Preparar bases de datos limpias para la prueba
    async with write_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE TABLE catalog_cards, catalog_locations CASCADE;"))
    async with read_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE TABLE catalog_cards, catalog_locations CASCADE;"))

    mongo_db = get_mongo_db()
    await mongo_db["cards_projection"].delete_many({})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ----------------------------------------------------------------------
        # Paso 1: Health check y conectividad de bases de datos
        # ----------------------------------------------------------------------
        health_resp = await client.get("/api/v1/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["status"] == "healthy"
        assert health_data["databases"]["postgres_master"] == "connected"
        assert health_data["databases"]["postgres_replica"] == "connected"
        assert health_data["databases"]["mongodb"] == "connected"
        assert "X-Correlation-ID" in health_resp.headers

        # ----------------------------------------------------------------------
        # Paso 2: Crear Carta (F-02 / US 2.1.1) con imagen 5:7
        # ----------------------------------------------------------------------
        image_5_7 = generate_image(500, 700, "orange")
        card_data = {
            "code": "PKA-FUE-001",
            "name": "Charmander",
            "cost": 2,
            "power": 3,
            "card_type": "FUE",
            "rarity": "COMUN",
            "ability_type": "AL_REVELARSE",
            "ability_description": "Otorga +1 de poder si juegas otra carta de Fuego",
            "ability_params_json": json.dumps({"bonus": 1, "target_type": "FUE"}),
        }
        create_card_resp = await client.post(
            "/api/v1/content/cards",
            data=card_data,
            files={"image": ("charmander.jpg", image_5_7, "image/jpeg")},
            headers={"Idempotency-Key": "key-create-charmander-001"},
        )
        assert create_card_resp.status_code == 201
        card_json = create_card_resp.json()
        assert card_json["code"] == "PKA-FUE-001"
        assert card_json["name"] == "Charmander"
        assert card_json["cost"] == 2
        assert card_json["power"] == 3
        assert card_json["image_url"].endswith(".webp")
        assert card_json["thumbnail_url"].endswith(".webp")

        # ----------------------------------------------------------------------
        # Paso 3: Buscar Carta en MongoDB (US 2.1.2)
        # ----------------------------------------------------------------------
        search_resp = await client.get("/api/v1/content/cards?name=Char")
        assert search_resp.status_code == 200
        search_json = search_resp.json()
        assert search_json["total"] >= 1
        assert any(c["code"] == "PKA-FUE-001" for c in search_json["items"])

        # Búsqueda vacía devuelve 200 OK con items: [] (nunca 404)
        empty_search = await client.get("/api/v1/content/cards?name=InexistenteXYZ")
        assert empty_search.status_code == 200
        assert empty_search.json()["items"] == []

        # ----------------------------------------------------------------------
        # Paso 4: Validar rechazo por costo inválido (> 6) formato RFC 7807
        # ----------------------------------------------------------------------
        invalid_cost_data = {
            "code": "PKA-FUE-002",
            "name": "Charizard Ilegal",
            "cost": 9,  # Fuera de rango [1..6]
            "power": 10,
            "card_type": "FUE",
            "rarity": "LEGENDARIA",
        }
        inv_cost_resp = await client.post(
            "/api/v1/content/cards",
            data=invalid_cost_data,
            files={"image": ("charizard.jpg", generate_image(500, 700), "image/jpeg")},
        )
        assert inv_cost_resp.status_code == 400
        inv_cost_json = inv_cost_resp.json()
        assert inv_cost_json["error"]["code"] == "CATALOG_INVALID_CARD_COST"
        assert len(inv_cost_json["error"]["details"]) > 0

        # ----------------------------------------------------------------------
        # Paso 5: Validar rechazo por proporción de imagen inválida (1:1 != 5:7)
        # ----------------------------------------------------------------------
        inv_ratio_data = {
            "code": "PKA-AGU-001",
            "name": "Squirtle",
            "cost": 1,
            "power": 2,
            "card_type": "AGU",
            "rarity": "COMUN",
        }
        inv_ratio_resp = await client.post(
            "/api/v1/content/cards",
            data=inv_ratio_data,
            files={"image": ("cuadrada.jpg", generate_image(500, 500), "image/jpeg")},
        )
        assert inv_ratio_resp.status_code == 400
        assert inv_ratio_resp.json()["error"]["code"] == "INVALID_IMAGE_ASPECT_RATIO"

        # ----------------------------------------------------------------------
        # Paso 6: Crear Ubicación de Juego (F-03 / US 2.1.3) con imagen 4:3
        # ----------------------------------------------------------------------
        location_data = {
            "name": "Monte Corona",
            "effect_type": "BONIFICACION_PODER",
            "effect_description": "+2 de poder a cartas tipo Lucha",
            "effect_params_json": json.dumps({"power_bonus": 2, "target_type": "LUC"}),
        }
        create_loc_resp = await client.post(
            "/api/v1/content/locations",
            data=location_data,
            files={"image": ("monte_corona.jpg", generate_image(800, 600, "green"), "image/jpeg")},
        )
        assert create_loc_resp.status_code == 201
        loc_json = create_loc_resp.json()
        assert loc_json["name"] == "Monte Corona"
        assert loc_json["effect"]["effect_type"] == "BONIFICACION_PODER"

        # ----------------------------------------------------------------------
        # Paso 7: Listar Ubicaciones
        # ----------------------------------------------------------------------
        list_loc_resp = await client.get("/api/v1/content/locations")
        assert list_loc_resp.status_code == 200
        locations = list_loc_resp.json()
        assert len(locations) >= 1
        assert any(loc["name"] == "Monte Corona" for loc in locations)
