"""Almacenamiento GridFS por ID reservado y Repositorio NoSQL de Catálogo."""

from asyncio import to_thread
import math
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from gridfs import AsyncGridFSBucket
from gridfs.errors import CorruptGridFile, FileExists, NoFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, PyMongoError

from src.database.mongodb.connection import get_mongo_db

from ..controllers.cartas_dtos import (
    CartaResponseDTO,
    CartaSearchQueryDTO,
    CartaSearchResponseDTO,
)
from ..domain.imagen_model import (
    MAX_IMAGE_BYTES,
    ArchivoImagen,
    ImagenAlmacenada,
    ImagenProcesada,
    ReferenciasImagen,
)
from ..ports.cartas_ports import ICartaRepository
from ..ports.imagen_ports import (
    AlmacenImagenPort,
    ArchivoNoExiste,
    ContenidoInconsistente,
    ErrorAlmacenamiento,
    ErrorGuardadoPar,
    ErrorImagen,
    ProcesadorImagenPort,
)

PREFIX = "gridfs:"


def _object_id(referencia: str) -> ObjectId:
    """Acepta únicamente la representación canónica de un ObjectId de GridFS."""
    if not referencia.startswith(PREFIX):
        raise ContenidoInconsistente("Referencia GridFS inválida")
    try:
        identificador = ObjectId(referencia.removeprefix(PREFIX))
    except InvalidId:
        raise ContenidoInconsistente("Referencia GridFS inválida") from None
    if referencia != PREFIX + str(identificador):
        raise ContenidoInconsistente("Referencia GridFS no canónica")
    return identificador


def _error_driver(error: PyMongoError) -> ErrorAlmacenamiento:
    """Clasifica indisponibilidad sin reproducir URL, credenciales ni comandos."""
    return ErrorAlmacenamiento(reintentable=isinstance(error, ConnectionFailure) or error.timeout)


class AlmacenImagenGridFS(AlmacenImagenPort):
    """Opera sobre un bucket inyectado. Un par pertenece a un solo llamador activo."""

    def __init__(self, bucket: AsyncGridFSBucket, procesador: ProcesadorImagenPort) -> None:
        """Recibe el bucket compartido y el verificador de contenido."""
        self._bucket = bucket
        self._procesador = procesador

    def reservar(self) -> ReferenciasImagen:
        """Reserva dos ObjectId antes de escribir para identificar resultados inciertos."""
        return ReferenciasImagen(PREFIX + str(ObjectId()), PREFIX + str(ObjectId()))

    async def recuperar(self, referencia: str) -> bytes:
        """Lee hasta el límite del contrato y comprueba longitud y fragmentos."""
        identificador = _object_id(referencia)
        try:
            async with await self._bucket.open_download_stream(identificador) as archivo:
                longitud = archivo.length
                if not isinstance(longitud, int) or not 0 < longitud <= MAX_IMAGE_BYTES:
                    raise ContenidoInconsistente("Longitud GridFS fuera de los límites")
                datos = await archivo.read(MAX_IMAGE_BYTES + 1)
                if len(datos) != longitud:
                    raise ContenidoInconsistente("Longitud GridFS discordante")
                return datos
        except NoFile:
            raise ArchivoNoExiste("No existe el archivo GridFS solicitado") from None
        except CorruptGridFile:
            raise ContenidoInconsistente("Los fragmentos GridFS son inconsistentes") from None
        except PyMongoError as error:
            raise _error_driver(error) from None

    async def _guardar(self, referencia: str, nombre: str, datos: bytes) -> None:
        """Reutiliza un ID completo solo cuando los bytes coinciden exactamente."""
        try:
            existente = await self.recuperar(referencia)
        except ArchivoNoExiste:
            try:
                await self._bucket.upload_from_stream_with_id(_object_id(referencia), nombre, datos)
            except FileExists:
                raise ContenidoInconsistente("Escritura en conflicto para el ID") from None
            except PyMongoError as error:
                raise _error_driver(error) from None
        else:
            if existente != datos:
                raise ContenidoInconsistente("El ID reservado contiene otros bytes")

    async def guardar_par(
        self,
        referencias: ReferenciasImagen,
        imagen: ImagenProcesada,
    ) -> ImagenAlmacenada:
        """Confirma ambos archivos o expone el progreso. No borra datos ante fallos."""
        if _object_id(referencias.original) == _object_id(referencias.miniatura):
            raise ContenidoInconsistente("Original y miniatura requieren IDs distintos")
        for archivo in (imagen.original, imagen.miniatura):
            if not 0 < len(archivo.datos) <= MAX_IMAGE_BYTES:
                raise ContenidoInconsistente("Binario fuera de los límites de almacenamiento")
        confirmadas: list[str] = []
        try:
            for referencia, nombre, archivo in (
                (referencias.original, "original", imagen.original),
                (referencias.miniatura, "thumbnail.webp", imagen.miniatura),
            ):
                await self._guardar(referencia, nombre, archivo.datos)
                confirmadas.append(referencia)
        except ErrorImagen as error:
            raise ErrorGuardadoPar(referencias, tuple(confirmadas), error) from None
        return ImagenAlmacenada(referencias, imagen.original.metadatos, imagen.miniatura.metadatos)

    async def verificar_par(self, imagen: ImagenAlmacenada) -> None:
        """Contrasta ambos binarios recuperados con los metadatos autoritativos."""
        original = await self.recuperar(imagen.referencias.original)
        miniatura = await self.recuperar(imagen.referencias.miniatura)
        await to_thread(
            self._procesador.verificar,
            ImagenProcesada(
                ArchivoImagen(original, imagen.original),
                ArchivoImagen(miniatura, imagen.miniatura),
            ),
        )

    async def eliminar(self, referencia: str) -> None:
        """Elimina por ID propio confirmado, fuera de cualquier escritura activa."""
        try:
            await self._bucket.delete(_object_id(referencia))
        except NoFile:
            # El driver elimina chunks de ese ID incluso si falta el documento files.
            return
        except PyMongoError as error:
            raise _error_driver(error) from None


# ------------------------------------------------------------------------------
# Adaptador NoSQL de Consulta y Búsqueda de Cartas (Catálogo / Jugador)
# ------------------------------------------------------------------------------

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
        "descripcion": "Su boca gigantesca conecta directamente con el más allá.",
        "imagen_url": "https://images.pokemontcg.io/swsh8/157_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/swsh8/157.png",
        "precio": 31.00,
        "activo": True,
    },
    {
        "id": "c9",
        "nombre": "Dragonite Primigenio",
        "codigo": "PKA-009",
        "tipo": "INC",
        "rareza": "RARA",
        "coste_energia": 3,
        "puntos_vida": 200,
        "puntos_ataque": 175,
        "descripcion": "Vuela tranquilamente sobre los mares socorriendo a los navegantes.",
        "imagen_url": "https://images.pokemontcg.io/pgo/49_hires.png",
        "imagen_miniatura_url": "https://images.pokemontcg.io/pgo/49.png",
        "precio": 21.00,
        "activo": True,
    },
    {
        "id": "c10",
        "nombre": "Arcanine Ígneo",
        "codigo": "PKA-010",
        "tipo": "FUE",
        "rareza": "INFRECUENTE",
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
        try:
            import asyncio
            db = self._get_db()
            # Preferir la colección de proyecciones desnormalizada oficial
            collection = db["cards_projection"] if "cards_projection" in await db.list_collection_names() else db["cards_catalog"]

            query: dict[str, Any] = {}
            if params.q:
                regex_pattern = {"$regex": params.q.strip(), "$options": "i"}
                query["$or"] = [
                    {"nombre": regex_pattern},
                    {"name": regex_pattern},
                    {"codigo": regex_pattern},
                    {"code": regex_pattern},
                    {"descripcion": regex_pattern},
                ]
            if params.tipo:
                val = params.tipo.value if hasattr(params.tipo, "value") else str(params.tipo)
                query["$or"] = query.get("$or", []) + [{"tipo": val}, {"card_type": val}]
            if params.rareza:
                val = params.rareza.value if hasattr(params.rareza, "value") else str(params.rareza)
                query["$or"] = query.get("$or", []) + [{"rareza": val}, {"rarity": val}]

            total = await asyncio.wait_for(collection.count_documents(query), timeout=0.5)
            if total > 0:
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
            pass

        # Búsqueda en memoria con catálogo semilla fallback
        filtradas = []
        q_term = (params.q or "").strip().lower()
        tipo_str = params.tipo.value if hasattr(params.tipo, "value") else str(params.tipo) if params.tipo else None
        rareza_str = params.rareza.value if hasattr(params.rareza, "value") else str(params.rareza) if params.rareza else None

        for c in CATALOGO_SEMILLA:
            if not c.get("activo", True):
                continue
            if q_term:
                nombre = str(c.get("nombre", "")).lower()
                codigo = str(c.get("codigo", "")).lower()
                desc = str(c.get("descripcion", "")).lower()
                if q_term not in nombre and q_term not in codigo and q_term not in desc:
                    continue
            if tipo_str and c.get("tipo") != tipo_str:
                continue
            if rareza_str and c.get("rareza") != rareza_str:
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
            for col_name in ("cards_projection", "cards_catalog"):
                if col_name in await db.list_collection_names():
                    collection = db[col_name]
                    doc = await collection.find_one({
                        "$or": [
                            {"_id": identificador},
                            {"id": identificador},
                            {"codigo": identificador},
                            {"code": identificador},
                        ]
                    })
                    if doc:
                        return CartaResponseDTO.model_validate(doc)
        except Exception:
            pass

        for c in CATALOGO_SEMILLA:
            if c.get("id") == identificador or c.get("codigo") == identificador:
                return CartaResponseDTO.model_validate(c)
        return None
