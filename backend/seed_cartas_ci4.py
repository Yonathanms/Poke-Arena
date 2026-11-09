"""Planea o aplica el lote CI-4 por la API autenticada, dentro del mismo proceso."""

import argparse
import asyncio
import gzip
import json
import logging
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from random import Random
from typing import Any, BinaryIO, cast
from urllib.parse import urlsplit

from bson import decode_file_iter
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.uri_parser import parse_uri
from sqlalchemy import text
from sqlalchemy.engine import RowMapping, make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.database.postgresql.destino_original import IDENTIDAD_SQL, identidad_original_valida
from src.database.postgresql.revisiones import REVISION_TIPO_CUENTA
from src.modules.catalogo.catalogo_module import crear_almacen_imagenes
from src.modules.catalogo.gestion_cartas.adapters.imagen_carta_adapter import ProcesadorImagenPillow
from src.modules.catalogo.gestion_cartas.adapters.mongo_card_projection import (
    MongoProyeccionCartas,
    verificar_indice_unico_codigo,
)
from src.modules.catalogo.gestion_cartas.controllers.cartas_dtos import CamposCrearCarta
from src.modules.catalogo.gestion_cartas.domain.carta_model import (
    RAREZAS_CARTA,
    TIPOS_CARTA,
    DatosCarta,
)
from src.modules.catalogo.gestion_cartas.domain.imagen_model import (
    MAX_IMAGE_BYTES,
    FormatoImagen,
    ImagenAlmacenada,
    ImagenProcesada,
    MetadatosImagen,
    ReferenciasImagen,
)
from src.modules.catalogo.gestion_cartas.ports.creacion_ports import ClaveCreacion
from src.modules.catalogo.gestion_cartas.services.cartas_service import _huella
from src.shared.config import Settings, get_settings
from src.shared.destinos_originales import (
    MONGO_ORIGINAL,
    PG_ORIGINAL,
    ROLES_MONGO_ORIGINAL,
    ROL_SQL_ORIGINAL,
    impedir_originales_en_pruebas,
    validar_acceso_original,
)

_IMAGEN = Path(__file__).resolve().parents[1] / "prueba" / "ip.png"
_RAREZAS = ("COMUN", "POCO_COMUN", "RARA", "LEGENDARIA")
_HABILIDAD = "HAB-000"
_ESPECIES = (
    "Pikachu",
    "Eevee",
    "Charmander",
    "Bulbasaur",
    "Squirtle",
    "Snorlax",
    "Psyduck",
    "Vulpix",
    "Jigglypuff",
    "Totodile",
    "Cyndaquil",
    "Chikorita",
    "Mudkip",
    "Treecko",
)
_TEMAS = (
    "Chispa",
    "Aurora",
    "Llama",
    "Brote",
    "Marea",
    "Siesta",
    "Cometa",
    "Bruma",
    "Trueno",
    "Ámbar",
    "Estrella",
    "Cristal",
)
_PG_PERSISTENTE = (15433, "pokearena_alembic_frontend_dev")
_MONGO_PERSISTENTE = (27029, "pokearena_catalog_frontend_dev")
_CARD_PATH = "/api/v1/content/cards"


class SeedInvalido(Exception):
    """El lote o el destino no se puede procesar de manera segura."""


@dataclass(frozen=True, slots=True)
class CartaPlan:
    """Solicitud normalizada con identidad de reintento estable."""

    datos: DatosCarta
    clave: str

    def campos(self) -> dict[str, str]:
        """Valida el contrato multipart y devuelve campos textuales para la API."""
        d = self.datos
        dto = CamposCrearCarta(
            name=d.nombre,
            cost=d.costo,
            power=d.poder,
            card_type=d.tipo,
            rarity=d.rareza,
            ability_code=d.habilidad,
        )
        return {k: str(v) for k, v in dto.model_dump().items()}


@dataclass(frozen=True, slots=True)
class Destino:
    """Par de destinos permitido sin almacenar credenciales en el reporte."""

    postgres: tuple[int, str]
    mongo: tuple[int, str]
    persistente: bool
    original: bool = False

    def etiquetas(self) -> dict[str, str]:
        """Presenta solo host, puerto y base."""
        return {
            "postgresql": f"127.0.0.1:{self.postgres[0]}/{self.postgres[1]}",
            "mongodb": f"127.0.0.1:{self.mongo[0]}/{self.mongo[1]}",
        }


@dataclass
class Reporte:
    """Estados mutuamente excluyentes del plan y verificación final."""

    existentes: set[str] = field(default_factory=set)
    creadas: set[str] = field(default_factory=set)
    pendientes: set[str] = field(default_factory=set)
    fallidas: dict[str, str] = field(default_factory=dict)

    def resumen(self, plan: list[CartaPlan]) -> dict[str, dict[str, int]]:
        """Cuenta cada resultado por rareza sin confundirlo con el catálogo global."""
        return {
            rareza: {
                estado: sum(c.datos.rareza == rareza and c.datos.nombre in nombres for c in plan)
                for estado, nombres in (
                    ("existentes", self.existentes),
                    ("creadas", self.creadas),
                    ("pendientes", self.pendientes),
                    ("fallidas", self.fallidas),
                )
            }
            for rareza in _RAREZAS
        }


def generar_plan(seed: int, lote: str) -> list[CartaPlan]:
    """Genera exactamente 20 solicitudes por rareza con el validador de Crear Carta."""
    if not re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", lote) or len(lote) > 24:
        raise SeedInvalido("Lote inválido. Usa hasta 24 caracteres alfanuméricos o guiones.")
    if set(_RAREZAS) != RAREZAS_CARTA:
        raise SeedInvalido("Las rarezas del catálogo ya no corresponden al contrato de CI-4.")
    rng = Random(seed)
    temas = rng.sample([(p, t) for p in _ESPECIES for t in _TEMAS], 80)
    tipos = (sorted(TIPOS_CARTA) * 14)[:80]
    rng.shuffle(tipos)
    plan: list[CartaPlan] = []
    for rareza in _RAREZAS:
        for ordinal in range(1, 21):
            indice = len(plan)
            especie, tema = temas[indice]
            datos = DatosCarta(
                f"CI-SEED-{lote}--{rareza}-{ordinal:02d}-{especie}-{tema}",
                rng.randint(0, 10),
                rng.randint(-20, 20),
                tipos[indice],
                rareza,
                _HABILIDAD,
            ).normalizados()
            carta = CartaPlan(datos, f"ci4:{lote}:{rareza}:{ordinal:02d}")
            carta.campos()
            plan.append(carta)
    return plan


def preparar_imagen() -> ImagenProcesada:
    """Valida la única fuente local con el mismo procesador del caso de uso."""
    if not _IMAGEN.is_file() or _IMAGEN.resolve() != _IMAGEN:
        raise SeedInvalido("Falta el archivo local prueba/ip.png o la ruta es un enlace.")
    try:
        with _IMAGEN.open("rb") as archivo:
            datos = archivo.read(MAX_IMAGE_BYTES + 1)
        return ProcesadorImagenPillow().procesar(datos)
    except Exception:
        raise SeedInvalido("Crear Carta no pudo validar prueba/ip.png.") from None


def _destino_mongo(url: str, usuario: str) -> tuple[int, str]:
    if urlsplit(url).scheme != "mongodb":
        raise SeedInvalido("MongoDB exige un único servidor directo de loopback.")
    uri = parse_uri(url, warn=False)
    hosts = uri["nodelist"]
    if (
        len(hosts) != 1
        or hosts[0][0] != "127.0.0.1"
        or hosts[0][1] in (None, 27017)
        or uri["username"] != usuario
        or not uri["password"]
        or not uri["database"]
        or {key.lower() for key in uri["options"]} - {"authsource", "directconnection"}
        or uri["options"].get("directConnection", True) is not True
    ):
        raise SeedInvalido("MongoDB fuera del aislamiento o sin credencial de aplicación.")
    return hosts[0][1], uri["database"]


def validar_destino(
    ajustes: Settings, proyeccion_url: str, *, confirmar_original: bool = False,
) -> Destino:
    """Mantiene el aislamiento salvo autorización explícita del par original exacto."""
    pg = make_url(ajustes.DATABASE_URL)
    if confirmar_original:
        try:
            impedir_originales_en_pruebas()
            if ajustes.ORIGINAL_RUNTIME != "api" or ajustes.MONGO_GRIDFS_BUCKET != "card_assets":
                raise ValueError
            ajustes.verificar_destinos("api")
            validar_acceso_original(
                pg, proyeccion_url, ajustes.MONGO_DB, ajustes.ENVIRONMENT, "outbox",
            )
        except ValueError:
            raise SeedInvalido("El opt-in IA-7 exige los destinos y roles originales exactos.") from None
        return Destino(PG_ORIGINAL[1:], MONGO_ORIGINAL[1:], persistente=True, original=True)
    if (
        pg.drivername != "postgresql+asyncpg"
        or pg.host != "127.0.0.1"
        or pg.port in (None, 5432)
        or not pg.database
        or pg.query
        or pg.username != "orm_media_test"
        or not pg.password
        or ajustes.ENVIRONMENT not in {"test", "development"}
    ):
        raise SeedInvalido("PostgreSQL fuera del aislamiento o sin credencial de aplicación.")
    postgres = (pg.port, pg.database)
    mongo = _destino_mongo(ajustes.MONGO_URL, "media_test")
    if (
        _destino_mongo(proyeccion_url, "projection_test") != mongo
        or ajustes.MONGO_DB != mongo[1]
        or ajustes.MONGO_GRIDFS_BUCKET != "card_assets"
    ):
        raise SeedInvalido("Medios y proyección deben corresponder al mismo MongoDB y bucket.")
    persistente = postgres == _PG_PERSISTENTE and mongo == _MONGO_PERSISTENTE
    descartable = (
        postgres[0] != _PG_PERSISTENTE[0]
        and mongo[0] != _MONGO_PERSISTENTE[0]
        and postgres[1].startswith("pokearena_alembic_ci4_test_")
        and mongo[1].startswith("pokearena_outbox_ci4_test_")
    )
    if not persistente and not descartable:
        raise SeedInvalido("El par de bases no corresponde a CI-4.")
    return Destino(postgres, mongo, persistente)


def validar_respaldos(directorio: Path | None, destino: Destino) -> None:
    """Comprueba backups de operador sin restaurar ni conectar a los motores."""
    if directorio is None:
        raise SeedInvalido("Apply persistente exige --backup-dir con ambos respaldos legibles.")
    pg = directorio / "postgres.dump"
    mongo = directorio / "mongo" / destino.mongo[1]
    try:
        restaurador = (
            ["docker", "exec", "-i", "pokearena-postgres", "pg_restore"]
            if destino.original else ["pg_restore"]
        )
        archivos_mongo = [
            mongo / f"{coleccion}.{extension}.gz"
            for coleccion in ("card_assets.files", "card_assets.chunks", "cards_projection")
            for extension in ("bson", "metadata.json")
        ]
        if destino.original:
            huellas = {
                ruta: huella
                for huella, ruta in (
                    linea.split("  ", 1)
                    for linea in (directorio / "SHA256SUMS").read_text().splitlines()
                )
            }
            for archivo in (pg, *archivos_mongo):
                with archivo.open("rb") as entrada:
                    digest = sha256()
                    for bloque in iter(lambda: entrada.read(1024 * 1024), b""):
                        digest.update(bloque)
                if digest.hexdigest() != huellas.get(archivo.relative_to(directorio).as_posix()):
                    raise SeedInvalido("El respaldo original no coincide con SHA256SUMS.")
        with pg.open("rb") as entrada:
            listado = subprocess.run(
                [*restaurador, "--list"], stdin=entrada, capture_output=True, check=True,
            ).stdout.decode()
        base = re.search(r"^;\s*dbname:\s*(\S+)\s*$", listado, re.MULTILINE)
        tablas = (
            "catalog_cards",
            "catalog_card_images",
            "shared_outbox",
            "shared_idempotency_records",
            "catalog_card_code_counters",
        )
        if (
            not base
            or base[1] != destino.postgres[1]
            or any(f"TABLE DATA public {tabla} " not in listado for tabla in tablas)
        ):
            raise SeedInvalido("El respaldo PostgreSQL no corresponde al destino y sus tablas.")
        with pg.open("rb") as entrada:
            subprocess.run(
                [*restaurador, "--file", os.devnull],
                stdin=entrada, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True,
            )
        for coleccion in ("card_assets.files", "card_assets.chunks", "cards_projection"):
            with gzip.open(mongo / f"{coleccion}.bson.gz", "rb") as archivo:
                for _ in decode_file_iter(cast(BinaryIO, archivo)):
                    pass
            with gzip.open(mongo / f"{coleccion}.metadata.json.gz", "rt") as archivo:
                if not isinstance(json.load(archivo).get("indexes"), list):
                    raise SeedInvalido("El respaldo MongoDB carece de metadatos de índices.")
    except SeedInvalido:
        raise
    except Exception:
        raise SeedInvalido(
            "No se pudieron leer ambos respaldos. Comprueba pg_restore y el dump."
        ) from None


@asynccontextmanager
async def _lectura(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.begin() as conn:
        await conn.execute(text("SET TRANSACTION READ ONLY"))
        yield conn


async def preflight_pg(engine: AsyncEngine, destino: Destino) -> dict[str, int]:
    """Verifica revisión, rol no administrativo, ACL, habilidad y contadores en solo lectura."""
    async with _lectura(engine) as conn:
        if destino.original:
            identidad = tuple((await conn.execute(IDENTIDAD_SQL)).one())
            ok = identidad_original_valida(identidad, ROL_SQL_ORIGINAL)
        else:
            ok = await conn.scalar(
                text("""
                SELECT current_database() = :base AND current_user = 'orm_media_test'
                  AND NOT (
                    rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
                  )
                FROM pg_roles WHERE rolname = current_user
                """),
                {"base": destino.postgres[1]},
            )
        revision = await conn.scalar(text("SELECT version_num FROM public.alembic_version"))
        if not ok or revision != REVISION_TIPO_CUENTA:
            raise SeedInvalido("PostgreSQL no es el destino real de aplicación en Alembic 014.")
        permisos = {
            "catalog_cards": ("SELECT", "INSERT"),
            "catalog_card_images": ("SELECT", "INSERT", "UPDATE"),
            "shared_idempotency_records": ("SELECT", "INSERT", "UPDATE"),
            "shared_outbox": ("SELECT", "INSERT", "UPDATE"),
            "catalog_abilities": ("SELECT",),
            "catalog_card_code_counters": ("SELECT", "UPDATE"),
        }
        for tabla, acciones in permisos.items():
            if not await conn.scalar(
                text("""
                SELECT bool_and(has_table_privilege(current_user, :tabla, accion))
                FROM unnest(CAST(:acciones AS text[])) AS accion
            """),
                {"tabla": f"public.{tabla}", "acciones": list(acciones)},
            ):
                raise SeedInvalido(f"Permisos insuficientes para {tabla}.")
        if not await conn.scalar(
            text("""
            SELECT EXISTS (SELECT FROM public.catalog_abilities WHERE code = 'HAB-000')
        """)
        ):
            raise SeedInvalido("La habilidad HAB-000 no existe en el destino.")
        filas = await conn.execute(
            text("""
            SELECT card_type, last_value FROM public.catalog_card_code_counters
        """)
        )
        return {tipo: ultimo for tipo, ultimo in filas}


async def _permisos_mongo(
    db: AsyncDatabase[dict[str, Any]],
    usuario: str,
    permisos: dict[str, set[str]],
) -> None:
    await db.command("ping")
    info = (await db.command("connectionStatus", showPrivileges=True))["authInfo"]
    if [u["user"] for u in info["authenticatedUsers"]] != [usuario] or any(
        rol["db"] != db.name for rol in info["authenticatedUserRoles"]
    ):
        raise SeedInvalido("La conexión MongoDB no usa un rol de aplicación aislado.")
    for coleccion, requeridos in permisos.items():
        presentes = {
            accion
            for permiso in info["authenticatedUserPrivileges"]
            if permiso["resource"].get("db") == db.name
            and permiso["resource"].get("collection") in ("", coleccion)
            for accion in permiso["actions"]
        }
        if not requeridos <= presentes:
            raise SeedInvalido(f"Permisos MongoDB insuficientes para {coleccion}.")


async def _leer_lote(
    engine: AsyncEngine,
    lote: str,
    plan: list[CartaPlan],
    imagen: ImagenProcesada,
    actor: str | None,
) -> dict[str, RowMapping]:
    """Cruza nombres, atributos y reservas de Crear Carta antes de reanudar."""
    esperado = {c.datos.nombre: c for c in plan}
    claves = {c.clave: c for c in plan}
    async with _lectura(engine) as conn:
        filas = (
            (
                await conn.execute(
                    text("""
            SELECT c.id, c.name, c.code, c.cost, c.power, c.rarity, c.card_type, c.version,
                   a.code AS habilidad, i.state, i.original_storage_key,
                   i.original_sha256, i.image_format, i.width, i.height, i.byte_size,
                   i.thumbnail_storage_key, i.thumbnail_format, i.thumbnail_width,
                   i.thumbnail_height, i.thumbnail_byte_size, o.status AS outbox_status
            FROM public.catalog_cards c JOIN public.catalog_abilities a ON a.id = c.ability_id
            LEFT JOIN public.catalog_card_images i ON i.id = c.image_id
            LEFT JOIN public.shared_outbox o ON o.aggregate_id = c.id
                AND o.event_type = 'CardCreated' AND o.aggregate_version = c.version
            WHERE starts_with(c.name, :prefijo)
        """),
                    {"prefijo": f"CI-SEED-{lote}--"},
                )
            )
            .mappings()
            .all()
        )
        registros = (
            (
                await conn.execute(
                    text("""
            SELECT actor_id, idempotency_key, request_hash, resource_id, response_status
            FROM public.shared_idempotency_records
            WHERE operation = :operacion AND starts_with(idempotency_key, :prefijo)
        """),
                    {"operacion": ClaveCreacion("", "").operacion, "prefijo": f"ci4:{lote}:"},
                )
            )
            .mappings()
            .all()
        )
    idempotencia = {}
    actores = set()
    for registro in registros:
        clave = registro["idempotency_key"]
        carta = claves.get(clave)
        if (
            clave in idempotencia
            or carta is None
            or registro["request_hash"] != _huella(carta.datos, imagen.original.datos)
        ):
            raise SeedInvalido("El lote ya tiene reservas incompatibles. Usa otro lote.")
        idempotencia[clave] = registro
        actores.add(registro["actor_id"])
    if len(actores) > 1 or actor is not None and actores - {actor}:
        raise SeedInvalido("El lote pertenece a otro administrador. Reanuda con el actor original.")

    existentes = {}
    for fila in filas:
        nombre = fila["name"]
        carta = esperado.get(nombre)
        if carta is None or nombre in existentes:
            raise SeedInvalido("El prefijo del lote contiene nombres ajenos o duplicados.")
        reserva = idempotencia.get(carta.clave)
        d = carta.datos
        if (
            reserva is None
            or reserva["resource_id"] != fila["id"]
            or reserva["response_status"] != 201
            or (fila["cost"], fila["power"], fila["card_type"], fila["rarity"], fila["habilidad"])
            != (d.costo, d.poder, d.tipo, d.rareza, d.habilidad)
            or fila["original_sha256"] != imagen.original.metadatos.sha256
        ):
            raise SeedInvalido(
                "Una carta del lote carece de procedencia o tiene atributos distintos."
            )
        existentes[nombre] = fila
    for clave, registro in idempotencia.items():
        if registro["response_status"] is not None and claves[clave].datos.nombre not in existentes:
            raise SeedInvalido("Una reserva confirmada no tiene su carta en el lote.")
    return existentes


@asynccontextmanager
async def _exclusivo(engine: AsyncEngine, lote: str) -> AsyncIterator[None]:
    # El bloqueo cubre el preflight y el lote entero, incluso entre actores distintos.
    huella = sha256(f"pokearena:ci4:{lote}".encode()).digest()
    llave = int.from_bytes(huella[:8], "big", signed=True)
    async with engine.connect() as conn:
        if not await conn.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": llave}):
            raise SeedInvalido("El lote está en ejecución en otra sesión.")
        try:
            await conn.commit()
            yield
        finally:
            try:
                await conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": llave})
            except BaseException:
                await conn.invalidate()
                raise


async def _proyectadas(
    coleccion: AsyncCollection[dict[str, Any]],
    filas: dict[str, RowMapping],
) -> set[str]:
    documentos = {
        doc["_id"]: doc
        async for doc in coleccion.find(
            {"_id": {"$in": [fila["id"] for fila in filas.values()]}},
            {"code": 1, "name": 1, "rarity": 1, "image_status": 1, "aggregate_version": 1},
        )
    }
    return {
        nombre
        for nombre, fila in filas.items()
        if fila["outbox_status"] == "PROCESSED"
        and (doc := documentos.get(fila["id"])) is not None
        and (
            doc.get("code"),
            doc.get("name"),
            doc.get("rarity"),
            doc.get("image_status"),
            doc.get("aggregate_version"),
        )
        == (fila["code"], nombre, fila["rarity"], "READY", fila["version"])
    }


async def _verificar_gridfs(filas: dict[str, RowMapping], reporte: Reporte) -> set[str]:
    almacen = crear_almacen_imagenes()
    validas = set()
    for nombre, f in filas.items():
        if f["state"] != "READY":
            continue
        try:
            referencias = ReferenciasImagen(f["original_storage_key"], f["thumbnail_storage_key"])
            if referencias.original == referencias.miniatura or f["thumbnail_format"] != "WEBP":
                raise SeedInvalido("Referencias o formato de miniatura incompatibles.")
            await almacen.verificar_par(
                ImagenAlmacenada(
                    referencias,
                    MetadatosImagen(
                        FormatoImagen(f["image_format"]),
                        f["width"],
                        f["height"],
                        f["byte_size"],
                        f["original_sha256"],
                    ),
                    MetadatosImagen(
                        FormatoImagen.WEBP,
                        f["thumbnail_width"],
                        f["thumbnail_height"],
                        f["thumbnail_byte_size"],
                    ),
                )
            )
        except Exception:
            reporte.fallidas[nombre] = "GridFS no verificable"
        else:
            validas.add(nombre)
    return validas


async def _actor(cliente: AsyncClient, plan: list[CartaPlan]) -> str:
    respuesta = await cliente.get("/api/v1/identity/me")
    if respuesta.status_code != 200 or respuesta.json().get("role") != "PLATFORM_ADMIN":
        raise SeedInvalido("Se requiere un Bearer administrativo del destino seleccionado.")
    habilidades = await cliente.get("/api/v1/content/abilities")
    if habilidades.status_code != 200 or not any(
        fila.get("code") == plan[0].datos.habilidad for fila in habilidades.json()
    ):
        raise SeedInvalido("HAB-000 no está disponible en la API autenticada.")
    actor: str = respuesta.json()["user_id"]
    return actor


async def _aplicar(
    cliente: AsyncClient,
    engine: AsyncEngine,
    coleccion: AsyncCollection[dict[str, Any]],
    args: argparse.Namespace,
    plan: list[CartaPlan],
    imagen: ImagenProcesada,
    contadores: dict[str, int],
) -> int:
    actor = await _actor(cliente, plan)
    async with _exclusivo(engine, args.lote):
        antes = await _leer_lote(engine, args.lote, plan, imagen, actor)
        _capacidad(plan, antes, contadores)
        reporte = Reporte(existentes=set(antes))
        validas = await _verificar_gridfs(antes, reporte)
        if validas != set(antes):
            raise SeedInvalido("El lote tiene cartas previas con imagen no verificable.")
        for carta in plan:
            nombre = carta.datos.nombre
            if nombre in antes:
                continue
            try:
                respuesta = await cliente.post(
                    _CARD_PATH,
                    headers={"Idempotency-Key": carta.clave},
                    data=carta.campos(),
                    files={"image": ("ip.png", imagen.original.datos, "image/png")},
                )
            except Exception:
                reporte.fallidas[nombre] = "Solicitud no confirmada"
            else:
                if respuesta.status_code != 201:
                    reporte.fallidas[nombre] = f"Crear Carta HTTP {respuesta.status_code}"
            if args.confirm_original_ia7 and nombre in reporte.fallidas:
                break
        filas = await _leer_lote(engine, args.lote, plan, imagen, actor)
        validas |= await _verificar_gridfs(
            {nombre: fila for nombre, fila in filas.items() if nombre not in antes},
            reporte,
        )
        limite = asyncio.get_running_loop().time() + args.espera
        while True:
            listas = (await _proyectadas(coleccion, filas)) & validas
            if listas == validas or asyncio.get_running_loop().time() >= limite:
                break
            await asyncio.sleep(0.5)
            filas = await _leer_lote(engine, args.lote, plan, imagen, actor)
        reporte.existentes = listas & set(antes)
        reporte.creadas = listas - set(antes)
        for nombre in listas:
            reporte.fallidas.pop(nombre, None)
        reporte.pendientes = {c.datos.nombre for c in plan} - listas - reporte.fallidas.keys()
        comunes = sum(filas[n]["rarity"] == "COMUN" for n in validas)
        print(
            json.dumps(
                {
                    "lote": args.lote,
                    "por_rareza": reporte.resumen(plan),
                    "cartas_sql": len(filas),
                    "nuevas_sql": len(set(filas) - set(antes)),
                    "pares_gridfs": len(validas),
                    "outbox_y_proyeccion": len(listas),
                    "comunes_elegibles": comunes,
                    "detalle_fallos": reporte.fallidas,
                    "detalle_pendientes": sorted(reporte.pendientes),
                },
                ensure_ascii=False,
            )
        )
        return 0 if len(listas) == 80 and comunes == 20 and not reporte.fallidas else 1


def _capacidad(
    plan: list[CartaPlan],
    existentes: dict[str, RowMapping],
    contadores: dict[str, int],
) -> None:
    faltantes = Counter(c.datos.tipo for c in plan if c.datos.nombre not in existentes)
    if any(
        tipo not in contadores or contadores[tipo] + cantidad > 999
        for tipo, cantidad in faltantes.items()
    ):
        raise SeedInvalido("Falta capacidad de códigos para completar el lote.")


async def ejecutar(args: argparse.Namespace, plan: list[CartaPlan], imagen: ImagenProcesada) -> int:
    """Ejecuta las comprobaciones y, solo en apply, llama al endpoint autenticado real."""
    token = os.environ.get("CI4_ADMIN_BEARER", "")
    if args.apply and not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise SeedInvalido(
            "CI4_ADMIN_BEARER debe contener el access_token opaco de Poké-Arena, "
            "sin prefijo Bearer, comillas ni espacios."
        )
    Settings.model_config["env_file"] = None
    get_settings.cache_clear()
    ajustes = get_settings()
    proyeccion_url = os.environ.get("CI4_PROJECTION_MONGO_URL", "")
    destino = validar_destino(ajustes, proyeccion_url, confirmar_original=args.confirm_original_ia7)
    print(json.dumps(destino.etiquetas()))
    if args.apply and destino.persistente:
        validar_respaldos(args.backup_dir, destino)
    from src.database.mongodb.connection import (
        close_mongo_connection, get_mongo_db, verificar_mongo_original,
    )
    from src.database.postgresql.connection import engine

    if engine.url != make_url(ajustes.DATABASE_URL):
        raise SeedInvalido("El engine efectivo de la API difiere del destino comprobado.")
    engine.echo = False
    try:
        contadores = await preflight_pg(engine, destino)
        media = get_mongo_db(conexion_directa=True)
        if destino.original:
            await verificar_mongo_original("api")
        await _permisos_mongo(
            media,
            ROLES_MONGO_ORIGINAL["api"] if destino.original else "media_test",
            {
                nombre: {"find", "insert", "remove", "createIndex", "listIndexes"}
                for nombre in ("card_assets.files", "card_assets.chunks")
            },
        )
        async with AsyncMongoClient[dict[str, Any]](
            proyeccion_url,
            directConnection=True,
            serverSelectionTimeoutMS=5000,
            timeoutMS=5000,
        ) as proyeccion:
            db = proyeccion[destino.mongo[1]]
            await _permisos_mongo(
                db,
                ROLES_MONGO_ORIGINAL["outbox"] if destino.original else "projection_test",
                {
                    "cards_projection": {"find", "insert", "update", "listIndexes"},
                },
            )
            if destino.original and await proyeccion.address != MONGO_ORIGINAL[:2]:
                raise SeedInvalido("El servidor de proyecciones difiere del destino original.")
            coleccion = db["cards_projection"]
            if destino.original:
                await verificar_indice_unico_codigo(coleccion)
            else:
                await MongoProyeccionCartas(coleccion).verificar_indices()
            if not args.apply:
                existentes = await _leer_lote(engine, args.lote, plan, imagen, None)
                _capacidad(plan, existentes, contadores)
                reporte = Reporte(
                    existentes=set(existentes),
                    pendientes={c.datos.nombre for c in plan} - existentes.keys(),
                )
                print(json.dumps({"modo": "dry-run", "por_rareza": reporte.resumen(plan)}))
                return 0
            transporte = None
            if not destino.original:
                from src.main import app

                transporte = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(
                transport=transporte,
                base_url="http://127.0.0.1:8000" if destino.original else "https://seed-ci4.invalid",
                trust_env=False,
                headers={"Authorization": f"Bearer {token}"},
            ) as cliente:
                return await _aplicar(cliente, engine, coleccion, args, plan, imagen, contadores)
    finally:
        await close_mongo_connection()
        await engine.dispose()


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    """Parsea el CLI y valida la segunda confirmación antes de abrir clientes."""
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="Modo predeterminado, solo lectura.")
    modo.add_argument("--apply", action="store_true", help="Crea las faltantes con la API real.")
    modo.add_argument(
        "--solo-plan", action="store_true", help="Valida imagen y plan sin conexiones."
    )
    confirmacion = parser.add_mutually_exclusive_group()
    confirmacion.add_argument("--confirm-isolated", action="store_true")
    confirmacion.add_argument("--confirm-original-ia7", action="store_true")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--lote", default="CI4-2026")
    parser.add_argument(
        "--espera", type=int, default=30, help="Segundos máximos de espera de Outbox."
    )
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args(argv)
    if args.apply != (args.confirm_isolated or args.confirm_original_ia7):
        parser.error("--apply exige exactamente una confirmación de destino.")
    if args.confirm_original_ia7 and (args.seed, args.lote) != (2026, "CI4-2026"):
        parser.error("El opt-in IA-7 solo autoriza el lote CI4-2026 con semilla 2026.")
    if not 0 <= args.espera <= 600:
        parser.error("--espera debe estar entre 0 y 600 segundos.")
    return args


def main() -> int:
    """Presenta el plan o un error sanitizado sin imprimir excepciones ni secretos."""
    args = argumentos()
    logging.disable(logging.CRITICAL)
    try:
        plan = generar_plan(args.seed, args.lote)
        imagen = preparar_imagen()
        meta = imagen.original.metadatos
        print(
            json.dumps(
                {
                    "lote": args.lote,
                    "seed": args.seed,
                    "imagen": "prueba/ip.png",
                    "formato": meta.formato,
                    "dimensiones": [meta.ancho, meta.alto],
                    "bytes": meta.tamano,
                    "sha256": meta.sha256,
                    "por_rareza": Counter(c.datos.rareza for c in plan),
                    "por_tipo": Counter(c.datos.tipo for c in plan),
                    "plan": [c.campos() | {"idempotency_key": c.clave} for c in plan],
                },
                ensure_ascii=False,
            )
        )
        if args.solo_plan:
            print("Plan local validado sin conexiones. Preflight de destinos pendiente.")
            return 0
        return asyncio.run(ejecutar(args, plan, imagen))
    except SeedInvalido as error:
        print(f"CI-4 detenido. {error}", file=sys.stderr)
    except Exception:
        print(
            "CI-4 detenido. No se pudo verificar la configuración o completar la operación.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
