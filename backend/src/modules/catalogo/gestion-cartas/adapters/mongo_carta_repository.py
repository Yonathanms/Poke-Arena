import math
from typing import Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.database.mongodb.connection import get_mongo_db
from src.modules.catalogo.gestion_cartas_bridge import (
    ICartaRepository,
    CartaResponseDTO,
    CartaSearchQueryDTO,
    CartaSearchResponseDTO,
)

# Catálogo fallback con datos iniciales oficiales para búsqueda inmediata
CATALOGO_SEMILLA: list[dict[str, Any]] = [
    {
        "id": "c1",
        "nombre": "Charizard Radiante",
        "codigo": "PKA-001",
        "tipo": "FUE",
        "rareza": "LEGENDARIA",
        "coste_energia": 4,
        "puntos_vida": 220,
        "puntos_ataque": 180,
        "descripcion": "Lanza llamaradas capaces de derretir cualquier defensa.",
        "imagen_url": "https://images.pokemontcg.io/pgo/11_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/pgo/11.png",
        "precio": 45.99,
        "activo": True,
    },
    {
        "id": "c2",
        "nombre": "Blastoise VMAX",
        "codigo": "PKA-002",
        "tipo": "AGU",
        "rareza": "EPICA",
        "coste_energia": 3,
        "puntos_vida": 210,
        "puntos_ataque": 160,
        "descripcion": "Sus cañones disparan chorros de agua a alta presión.",
        "imagen_url": "https://images.pokemontcg.io/swsh45sv/SV125_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh45sv/SV125.png",
        "precio": 38.50,
        "activo": True,
    },
    {
        "id": "c3",
        "nombre": "Venusaur Primigenio",
        "codigo": "PKA-003",
        "tipo": "PLA",
        "rareza": "EPICA",
        "coste_energia": 3,
        "puntos_vida": 230,
        "puntos_ataque": 150,
        "descripcion": "La flor de su lomo absorbe la energía solar para atacar.",
        "imagen_url": "https://images.pokemontcg.io/swsh45sv/SV124_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh45sv/SV124.png",
        "precio": 32.00,
        "activo": True,
    },
    {
        "id": "c4",
        "nombre": "Pikachu V",
        "codigo": "PKA-004",
        "tipo": "ELE",
        "rareza": "RARA",
        "coste_energia": 2,
        "puntos_vida": 140,
        "puntos_ataque": 120,
        "descripcion": "Acumula electricidad en sus mejillas y la libera en tormenta.",
        "imagen_url": "https://images.pokemontcg.io/swsh4/43_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh4/43.png",
        "precio": 18.00,
        "activo": True,
    },
    {
        "id": "c5",
        "nombre": "Mewtwo GX",
        "codigo": "PKA-005",
        "tipo": "PSI",
        "rareza": "LEGENDARIA",
        "coste_energia": 4,
        "puntos_vida": 190,
        "puntos_ataque": 200,
        "descripcion": "Creado por manipulación genética, domina poderes psíquicos.",
        "imagen_url": "https://images.pokemontcg.io/sm35/39_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/sm35/39.png",
        "precio": 55.00,
        "activo": True,
    },
    {
        "id": "c6",
        "nombre": "Lucario VSTAR",
        "codigo": "PKA-006",
        "tipo": "LUC",
        "rareza": "EPICA",
        "coste_energia": 3,
        "puntos_vida": 180,
        "puntos_ataque": 170,
        "descripcion": "Controla ondas aurales para predecir los movimientos del rival.",
        "imagen_url": "https://images.pokemontcg.io/swsh9/79_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh9/79.png",
        "precio": 27.50,
        "activo": True,
    },
    {
        "id": "c7",
        "nombre": "Snorlax Glotón",
        "codigo": "PKA-007",
        "tipo": "INC",
        "rareza": "RARA",
        "coste_energia": 2,
        "puntos_vida": 250,
        "puntos_ataque": 110,
        "descripcion": "No queda satisfecho hasta comerse 400 kilos de comida al día.",
        "imagen_url": "https://images.pokemontcg.io/swsh4/131_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh4/131.png",
        "precio": 14.00,
        "activo": True,
    },
    {
        "id": "c8",
        "nombre": "Gengar Gigamax",
        "codigo": "PKA-008",
        "tipo": "PSI",
        "rareza": "EPICA",
        "coste_energia": 3,
        "puntos_vida": 175,
        "puntos_ataque": 165,
        "descripcion": "Su boca parece una puerta directa al inframundo.",
        "imagen_url": "https://images.pokemontcg.io/swsh8/157_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh8/157.png",
        "precio": 36.00,
        "activo": True,
    },
    {
        "id": "c9",
        "nombre": "Rayquaza VMAX",
        "codigo": "PKA-009",
        "tipo": "ELE",
        "rareza": "LEGENDARIA",
        "coste_energia": 4,
        "puntos_vida": 200,
        "puntos_ataque": 210,
        "descripcion": "Habita en la capa de ozono y desciende envuelto en relámpagos.",
        "imagen_url": "https://images.pokemontcg.io/swsh7/111_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh7/111.png",
        "precio": 68.00,
        "activo": True,
    },
    {
        "id": "c10",
        "nombre": "Arcanine Ígneo",
        "codigo": "PKA-010",
        "tipo": "FUE",
        "rareza": "RARA",
        "coste_energia": 2,
        "puntos_vida": 160,
        "puntos_ataque": 130,
        "descripcion": "Corre con una agilidad legendaria envuelto en llamas doradas.",
        "imagen_url": "https://images.pokemontcg.io/swsh9/29_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh9/29.png",
        "precio": 16.50,
        "activo": True,
    },
    {
        "id": "c11",
        "nombre": "Gyarados Furia",
        "codigo": "PKA-011",
        "tipo": "AGU",
        "rareza": "RARA",
        "coste_energia": 3,
        "puntos_vida": 195,
        "puntos_ataque": 155,
        "descripcion": "Capaz de arrasar ciudades enteras en un ataque de furia desatada.",
        "imagen_url": "https://images.pokemontcg.io/swsh7/29_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh7/29.png",
        "precio": 22.00,
        "activo": True,
    },
    {
        "id": "c12",
        "nombre": "Eevee Arcoíris",
        "codigo": "PKA-012",
        "tipo": "INC",
        "rareza": "INFRECUENTE",
        "coste_energia": 1,
        "puntos_vida": 110,
        "puntos_ataque": 80,
        "descripcion": "Posee una estructura genética inestable y llena de potencial.",
        "imagen_url": "https://images.pokemontcg.io/swsh45/47_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh45/47.png",
        "precio": 9.50,
        "activo": True,
    },
    {
        "id": "c13",
        "nombre": "Machamp Dinamax",
        "codigo": "PKA-013",
        "tipo": "LUC",
        "rareza": "EPICA",
        "coste_energia": 3,
        "puntos_vida": 185,
        "puntos_ataque": 165,
        "descripcion": "Puede asestar más de mil golpes contundentes en solo dos segundos.",
        "imagen_url": "https://images.pokemontcg.io/swsh10/73_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh10/73.png",
        "precio": 29.00,
        "activo": True,
    },
    {
        "id": "c14",
        "nombre": "Zapdos Ancestral",
        "codigo": "PKA-014",
        "tipo": "ELE",
        "rareza": "LEGENDARIA",
        "coste_energia": 3,
        "puntos_vida": 170,
        "puntos_ataque": 175,
        "descripcion": "Pájaro legendario que controla las nubes de tormenta y los truenos.",
        "imagen_url": "https://images.pokemontcg.io/swsh10/41_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh10/41.png",
        "precio": 49.00,
        "activo": True,
    },
    {
        "id": "c15",
        "nombre": "Celebi Guardián",
        "codigo": "PKA-015",
        "tipo": "PLA",
        "rareza": "LEGENDARIA",
        "coste_energia": 2,
        "puntos_vida": 150,
        "puntos_ataque": 140,
        "descripcion": "Guardián del bosque con el don de viajar en el tiempo.",
        "imagen_url": "https://images.pokemontcg.io/swsh8/7_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh8/7.png",
        "precio": 42.00,
        "activo": True,
    },
]


class MongoCartaRepository(ICartaRepository):
    """Adaptador de persistencia MongoDB para Catálogo de lectura rápida."""

    def __init__(self, db: AsyncIOMotorDatabase[Any] | None = None) -> None:
        self._db = db

    def _get_db(self) -> AsyncIOMotorDatabase[Any]:
        if self._db is None:
            return get_mongo_db()
        return self._db

    async def buscar_cartas(self, params: CartaSearchQueryDTO) -> CartaSearchResponseDTO:
        """Busca cartas aplicando filtros de texto, tipo y rareza."""
        # Intenta consultar MongoDB con timeout estricto si está disponible; de lo contrario usa catálogo local
        try:
            import asyncio
            db = self._get_db()
            collection = db["cards_catalog"]

            query: dict[str, Any] = {"activo": True}
            if params.q:
                regex_pattern = {"$regex": params.q.strip(), "$options": "i"}
                query["$or"] = [
                    {"nombre": regex_pattern},
                    {"codigo": regex_pattern},
                    {"descripcion": regex_pattern},
                ]
            if params.tipo:
                query["tipo"] = params.tipo.value
            if params.rareza:
                query["rareza"] = params.rareza.value

            # Timeout de 500ms para no bloquear si no hay base de datos conectada
            total = await asyncio.wait_for(collection.count_documents(query), timeout=0.5)
            skip = (params.pagina - 1) * params.limite

            cursor = collection.find(query).skip(skip).limit(params.limite)
            docs = await asyncio.wait_for(cursor.to_list(length=params.limite), timeout=0.5)

            if docs:
                items = [CartaResponseDTO.model_validate(doc) for doc in docs]
                total_paginas = max(1, math.ceil(total / params.limite))
                return CartaSearchResponseDTO(
                    items=items,
                    total=total,
                    pagina=params.pagina,
                    limite=params.limite,
                    total_paginas=total_paginas,
                )
        except Exception:
            # Fallback inmediato sin bloquear la respuesta
            pass

        # Búsqueda en memoria resiliente
        filtradas = []
        q_term = (params.q or "").strip().lower()

        for c in CATALOGO_SEMILLA:
            if not c.get("activo", True):
                continue
            if q_term:
                nombre = str(c.get("nombre", "")).lower()
                codigo = str(c.get("codigo", "")).lower()
                desc = str(c.get("descripcion", "")).lower()
                if q_term not in nombre and q_term not in codigo and q_term not in desc:
                    continue
            if params.tipo and c.get("tipo") != params.tipo.value:
                continue
            if params.rareza and c.get("rareza") != params.rareza.value:
                continue
            filtradas.append(c)

        total = len(filtradas)
        total_paginas = max(1, math.ceil(total / params.limite))
        inicio = (params.pagina - 1) * params.limite
        fin = inicio + params.limite
        pagina_items = filtradas[inicio:fin]

        items = [CartaResponseDTO.model_validate(item) for item in pagina_items]
        return CartaSearchResponseDTO(
            items=items,
            total=total,
            pagina=params.pagina,
            limite=params.limite,
            total_paginas=total_paginas,
        )

    async def obtener_por_id_o_codigo(self, identificador: str) -> CartaResponseDTO | None:
        try:
            db = self._get_db()
            collection = db["cards_catalog"]
            doc = await collection.find_one({
                "$or": [{"id": identificador}, {"codigo": identificador}]
            })
            if doc:
                return CartaResponseDTO.model_validate(doc)
        except Exception:
            pass

        for c in CATALOGO_SEMILLA:
            if c.get("id") == identificador or c.get("codigo") == identificador:
                return CartaResponseDTO.model_validate(c)
        return None
