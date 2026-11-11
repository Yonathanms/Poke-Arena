#!/usr/bin/env python3
"""Script para poblar y actualizar las tablas maestras de Tipos y Rarezas en PostgreSQL.

Inserta o actualiza de manera idempotente los catálogos en:
- public.catalog_card_types (FUE, AGU, PLA, ELE, PSI, LUC)
- public.catalog_card_rarities (COMUN, POCO_COMUN, RARA, LEGENDARIA)

Gracias a la clave foránea con ON UPDATE CASCADE, si en el futuro se modifica un código,
todas las cartas vinculadas en catalog_cards se actualizarán automáticamente.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Asegurar salida UTF-8 en terminales Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def cargar_entorno() -> dict[str, str]:
    """Carga variables del archivo .env en la raíz del proyecto."""
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


DEFAULT_CARD_TYPES = [
    {"code": "FUE", "name": "Fuego", "description": "Energía y ataques ígneos"},
    {"code": "AGU", "name": "Agua", "description": "Ataques acuáticos y curación"},
    {"code": "PLA", "name": "Planta", "description": "Fuerza natural y absorción"},
    {"code": "ELE", "name": "Eléctrico", "description": "Ataques relámpago y parálisis"},
    {"code": "PSI", "name": "Psíquico", "description": "Poderes mentales y control"},
    {"code": "LUC", "name": "Lucha", "description": "Fuerza física y combate directo"},
]

DEFAULT_CARD_RARITIES = [
    {"code": "COMUN", "name": "Común"},
    {"code": "POCO_COMUN", "name": "Poco Común"},
    {"code": "RARA", "name": "Rara"},
    {"code": "LEGENDARIA", "name": "Legendaria"},
]


async def poblar_catalogos(database_url: str) -> None:
    """Inserta o actualiza los tipos y rarezas en PostgreSQL."""
    print(f"\n[+] Conectando a PostgreSQL...")
    engine = create_async_engine(database_url, echo=False)

    try:
        async with engine.begin() as conn:
            # 1. Poblar Tipos
            print("[+] Poblando tabla maestra: catalog_card_types...")
            for t in DEFAULT_CARD_TYPES:
                await conn.execute(
                    text("""
                        INSERT INTO public.catalog_card_types (code, name, description)
                        VALUES (:code, :name, :description)
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description;
                    """),
                    t,
                )
                print(f"    ✓ Tipo: {t['code']} - {t['name']}")

            # 2. Poblar Rarezas
            print("\n[+] Poblando tabla maestra: catalog_card_rarities...")
            for r in DEFAULT_CARD_RARITIES:
                await conn.execute(
                    text("""
                        INSERT INTO public.catalog_card_rarities (code, name)
                        VALUES (:code, :name)
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name;
                    """),
                    r,
                )
                print(f"    ✓ Rareza: {r['code']} - {r['name']}")

            # 3. Resumen de verificación
            res_tipos = (await conn.execute(text("SELECT count(*) FROM public.catalog_card_types;"))).scalar()
            res_rarezas = (await conn.execute(text("SELECT count(*) FROM public.catalog_card_rarities;"))).scalar()
            res_cartas = (await conn.execute(text("SELECT count(*) FROM public.catalog_cards;"))).scalar()

            print(f"\n=======================================================")
            print(f" ✓ Sincronización exitosa:")
            print(f"   - Tipos registrados:   {res_tipos}")
            print(f"   - Rarezas registradas: {res_rarezas}")
            print(f"   - Cartas validadas:    {res_cartas}")
            print(f"=======================================================\n")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Poblar tipos elementales y rarezas en PostgreSQL.")
    parser.add_argument("--url", default=None, help="Cadena de conexión asyncpg a PostgreSQL")
    args = parser.parse_args()

    env_vars = cargar_entorno()
    db_url = args.url or env_vars.get("DATABASE_URL")
    if not db_url:
        print("[!] Error: No se encontró DATABASE_URL en .env ni como argumento.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(poblar_catalogos(db_url))


if __name__ == "__main__":
    main()

