#!/usr/bin/env python3
"""Script para volcar y exportar todas las imágenes de cartas desde MongoDB GridFS.

Guarda tanto las versiones originales (5:7 WebP) como las miniaturas de combate
(200x280 WebP) en la carpeta de destino con nombres legibles (código y nombre de carta).
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient
import gridfs

# Rutas base relativas a la raíz del repositorio
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "resources" / "images_cartas_mongo"


def sanitizar_nombre(texto: str) -> str:
    """Convierte texto en un nombre seguro para el sistema de archivos."""
    limpio = re.sub(r'[^\w\s-]', '', texto).strip()
    return re.sub(r'[-\s]+', '_', limpio)


def cargar_entorno() -> dict[str, str]:
    """Carga variables del archivo .env de la raíz si existe."""
    env_path = ROOT_DIR / ".env"
    valores: dict[str, str] = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8", errors="replace") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    valores[k.strip()] = v.strip().strip("'\"")
    return valores


async def obtener_mapa_cartas_sql(db_url: str) -> dict[str, tuple[str, str]]:
    """Mapea ObjectId de GridFS con (código_carta, nombre_carta, tipo_imagen)."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(db_url)
        mapeo: dict[str, tuple[str, str]] = {}
        async with engine.connect() as conn:
            query = text("""
                SELECT c.code, c.name, img.original_storage_key, img.thumbnail_storage_key
                FROM catalog_cards c
                JOIN catalog_card_images img ON c.image_id = img.id;
            """)
            filas = (await conn.execute(query)).mappings().all()
            for r in filas:
                codigo = str(r["code"])
                nombre = sanitizar_nombre(str(r["name"] or "carta"))
                orig = str(r["original_storage_key"] or "").removeprefix("gridfs:")
                thumb = str(r["thumbnail_storage_key"] or "").removeprefix("gridfs:")
                if orig:
                    mapeo[orig] = (codigo, f"{codigo}_{nombre}_original.webp")
                if thumb:
                    mapeo[thumb] = (codigo, f"{codigo}_{nombre}_thumbnail.webp")
        await engine.dispose()
        return mapeo
    except Exception as exc:
        print(f"[AVISO] No se pudo consultar PostgreSQL ({exc}). Se usarán nombres por defecto.")
        return {}


def exportar_imagenes_mongo(output_dir: Path, bucket_name: str = "card_assets") -> int:
    """Extrae todos los binarios de GridFS y los guarda en disco."""
    env = cargar_entorno()
    mongo_url = env.get(
        "MONGO_URL",
        "mongodb://mongoadmin:mongo_secure_pass_2026@localhost:27017/pokearena_catalog_frontend_dev?authSource=admin",
    )
    mongo_db_name = env.get("MONGO_DB", "pokearena_catalog_frontend_dev")
    db_url = env.get(
        "DATABASE_URL",
        "postgresql+asyncpg://orm_media_test:app_pass_2026@localhost:5432/pokearena_alembic_frontend_dev",
    )

    print("=" * 65)
    print("  VOLCADO DE IMÁGENES DE CARTAS (MongoDB GridFS -> Disco)")
    print("=" * 65)
    print(f"  Base de datos:  {mongo_db_name}")
    print(f"  Bucket GridFS:  {bucket_name}")
    print(f"  Destino local:  {output_dir}")
    print("-" * 65)

    # 1. Asegurar que existe el directorio de destino
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Consultar mapeo de nombres de cartas si Postgres está accesible
    mapeo_nombres: dict[str, tuple[str, str]] = {}
    try:
        mapeo_nombres = asyncio.run(obtener_mapa_cartas_sql(db_url))
    except Exception:
        pass

    # 3. Conectar a MongoDB y GridFS
    try:
        client: MongoClient[Any] = MongoClient(mongo_url, directConnection=True)
        db = client[mongo_db_name]
        fs = gridfs.GridFSBucket(db, bucket_name=bucket_name)
        files_col = db[f"{bucket_name}.files"]
        total_archivos = files_col.count_documents({})
    except Exception as err:
        print(f"\n[ERROR] No se pudo conectar a MongoDB: {err}")
        return 1

    if total_archivos == 0:
        print(f"\n[INFO] No se encontraron archivos en la colección '{bucket_name}.files'.")
        return 0

    print(f"\n[MongoDB] Se encontraron {total_archivos} archivos en '{bucket_name}.files'. Descargando...\n")

    descargados = 0
    bytes_totales = 0

    for doc in files_col.find().sort("_id", 1):
        file_id = doc["_id"]
        file_id_str = str(file_id)
        filename_orig = str(doc.get("filename", "imagen.webp"))
        length = doc.get("length", 0)

        # Determinar nombre del archivo final
        if file_id_str in mapeo_nombres:
            _, nombre_archivo = mapeo_nombres[file_id_str]
        else:
            # Fallback por ObjectId si no está mapeado a una carta específica
            sufijo = "thumbnail.webp" if "thumb" in filename_orig else "original.webp"
            nombre_archivo = f"card_{file_id_str}_{sufijo}"

        destino = output_dir / nombre_archivo

        try:
            with open(destino, "wb") as f_out:
                fs.download_to_stream(file_id, f_out)
            tamano_kb = length / 1024
            print(f"  ✓ {nombre_archivo:<45} ({tamano_kb:>6.1f} KB) -> ID: {file_id_str}")
            descargados += 1
            bytes_totales += length
        except Exception as err_descarga:
            print(f"  ✗ Error descargando {file_id_str} ({filename_orig}): {err_descarga}")

    print("-" * 65)
    print(f"[ÉXITO] {descargados}/{total_archivos} imágenes volcadas correctamente.")
    print(f"[INFO]  Total transferido: {bytes_totales / 1024:.2f} KB en: {output_dir}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vuelca imágenes de cartas de MongoDB GridFS a la carpeta resources/images_cartas_mongo"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directorio de destino para las imágenes exportadas",
    )
    parser.add_argument(
        "--bucket",
        "-b",
        type=str,
        default="card_assets",
        help="Nombre del bucket GridFS (por defecto: card_assets)",
    )
    args = parser.parse_args()
    return exportar_imagenes_mongo(args.output_dir, args.bucket)


if __name__ == "__main__":
    sys.exit(main())

