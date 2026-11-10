#!/usr/bin/env python3
"""Herramienta para ensamblar arte 5:7 e inyectar N cartas en Poké-Arena.

Superpone de forma inteligente:
1. Fondo degradado elemental + halo atmosférico en la ventana central del marco.
2. Sprite del Pokémon correspondiente a la carpeta del tipo elemental.
3. Marco según la rareza sorteada (`rareza_comun`, `rareza_pococomun`, `rareza_rara`, `rareza_legendario`).
4. Escudo de tipo elemental (`tipo_fuego`, `tipo_agua`, etc.) en la franja superior de la ventana.

Garantiza resolución exacta 700x980 (proporción 5:7, >= 600x840, <= 5 MB),
crea cada carta mediante el caso de uso oficial `CrearCarta` (PostgreSQL + GridFS)
y sincroniza la proyección de lectura `cards_projection` en MongoDB.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import random
import re
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw

# Asegurar salida UTF-8 en terminales Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# CONFIGURACIÓN PRINCIPAL (Puedes cambiar CANTIDAD_CARTAS_DEFAULT aquí o por CLI)
# ==============================================================================
CANTIDAD_CARTAS_DEFAULT: int = 25

# Dimensiones 5:7 válidas para US 2.1.1 (mínimo 600x840; 700*7 == 980*5 == 4900)
CARD_WIDTH: int = 700
CARD_HEIGHT: int = 980

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
ASSETS_DIR = ROOT_DIR / "resources" / "image_ensambler"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@dataclass(frozen=True, slots=True)
class ConfigRareza:
    """Configuración de rareza, probabilidad matemática, marco y rangos de stats."""

    codigo: str
    etiqueta: str
    probabilidad: float
    archivo_marco: str
    costo_min: int
    costo_max: int
    poder_min: int
    poder_max: int


@dataclass(frozen=True, slots=True)
class ConfigTipo:
    """Configuración del tipo elemental, carpeta de sprites, escudo y paleta de fondo."""

    codigo: str
    etiqueta: str
    carpeta_sprites: str
    archivo_escudo: str
    color_superior: tuple[int, int, int]
    color_medio: tuple[int, int, int]
    color_inferior: tuple[int, int, int]


# Relación de probabilidad matemática decreciente (suma = 1.00):
# Común (55%) > Poco Común (27%) > Rara (13%) > Legendaria (5%)
RAREZAS_CONFIG: tuple[ConfigRareza, ...] = (
    ConfigRareza(
        codigo="COMUN",
        etiqueta="Común",
        probabilidad=0.55,
        archivo_marco="rareza_comun.png",
        costo_min=1,
        costo_max=3,
        poder_min=1,
        poder_max=6,
    ),
    ConfigRareza(
        codigo="POCO_COMUN",
        etiqueta="Poco Común",
        probabilidad=0.27,
        archivo_marco="rareza_pococomun.png",
        costo_min=2,
        costo_max=5,
        poder_min=4,
        poder_max=10,
    ),
    ConfigRareza(
        codigo="RARA",
        etiqueta="Rara",
        probabilidad=0.13,
        archivo_marco="rareza_rara.png",
        costo_min=4,
        costo_max=7,
        poder_min=8,
        poder_max=15,
    ),
    ConfigRareza(
        codigo="LEGENDARIA",
        etiqueta="Legendaria",
        probabilidad=0.05,
        archivo_marco="rareza_legendario.png",
        costo_min=6,
        costo_max=10,
        poder_min=14,
        poder_max=20,
    ),
)

TIPOS_CONFIG: dict[str, ConfigTipo] = {
    "FUE": ConfigTipo(
        codigo="FUE",
        etiqueta="Fuego",
        carpeta_sprites="fuego",
        archivo_escudo="tipo_fuego.png",
        color_superior=(135, 20, 24),
        color_medio=(228, 87, 25),
        color_inferior=(255, 206, 52),
    ),
    "AGU": ConfigTipo(
        codigo="AGU",
        etiqueta="Agua",
        carpeta_sprites="agua",
        archivo_escudo="tipo_agua.png",
        color_superior=(15, 52, 110),
        color_medio=(18, 137, 195),
        color_inferior=(138, 228, 245),
    ),
    "PLA": ConfigTipo(
        codigo="PLA",
        etiqueta="Planta",
        carpeta_sprites="planta",
        archivo_escudo="tipo_planta.png",
        color_superior=(20, 82, 48),
        color_medio=(58, 162, 95),
        color_inferior=(215, 247, 116),
    ),
    "ELE": ConfigTipo(
        codigo="ELE",
        etiqueta="Eléctrico",
        carpeta_sprites="electrico",
        archivo_escudo="tipo_electrico.png",
        color_superior=(48, 42, 128),
        color_medio=(176, 112, 38),
        color_inferior=(255, 232, 36),
    ),
    "PSI": ConfigTipo(
        codigo="PSI",
        etiqueta="Psíquico",
        carpeta_sprites="psiquico",
        archivo_escudo="tipo_psiquico.png",
        color_superior=(123, 31, 162),
        color_medio=(194, 100, 140),
        color_inferior=(255, 213, 46),
    ),
    "LUC": ConfigTipo(
        codigo="LUC",
        etiqueta="Lucha",
        carpeta_sprites="lucha",
        archivo_escudo="tipo_lucha.png",
        color_superior=(96, 40, 20),
        color_medio=(192, 88, 38),
        color_inferior=(248, 198, 78),
    ),
}


def cargar_entorno_desarrollo() -> None:
    """Carga variables de .env si existe y asegura valores por defecto de desarrollo."""
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8", errors="replace") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    clave = k.strip()
                    valor = v.strip().strip("'\"")
                    if valor and clave not in os.environ:
                        os.environ[clave] = valor

    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://orm_media_test:app_pass_2026@localhost:5432/pokearena_alembic_frontend_dev",
    )
    os.environ.setdefault(
        "MONGO_URL",
        "mongodb://mongoadmin:mongo_secure_pass_2026@localhost:27017/pokearena_catalog_frontend_dev?authSource=admin&directConnection=true",
    )
    os.environ.setdefault("MONGO_DB", "pokearena_catalog_frontend_dev")
    os.environ.setdefault("MONGO_GRIDFS_BUCKET", "card_assets")


def formatear_nombre_pokemon(ruta_sprite: Path) -> str:
    """Extrae un nombre limpio y legible a partir del archivo de sprite."""
    base = ruta_sprite.stem
    # Remover sufijos técnicos como _HOME, _hembra, _macho
    base = re.sub(r"_HOME(?:_hembra|_macho)?$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"_(?:hembra|macho)$", "", base, flags=re.IGNORECASE)
    nombre = base.replace("_", " ").strip()
    return nombre[:100] if nombre else "Pokémon Misterioso"


def sortear_rareza(rng: random.Random) -> ConfigRareza:
    """Selecciona una rareza respetando la distribución de probabilidad matemática."""
    pesos = [r.probabilidad for r in RAREZAS_CONFIG]
    return rng.choices(RAREZAS_CONFIG, weights=pesos, k=1)[0]


def _detectar_ventana_transparente(marco: Image.Image) -> tuple[int, int, int, int]:
    """Detecta los bordes internos de la ventana transparente del marco."""
    w, h = marco.size
    cx, cy = w // 2, int(h * 0.40)
    izquierda, derecha, arriba, abajo = cx, cx, cy, cy
    while izquierda > 0 and marco.getpixel((izquierda, cy))[3] < 200:
        izquierda -= 1
    while derecha < w - 1 and marco.getpixel((derecha, cy))[3] < 200:
        derecha += 1
    while arriba > 0 and marco.getpixel((cx, arriba))[3] < 200:
        arriba -= 1
    while abajo < h - 1 and marco.getpixel((cx, abajo))[3] < 200:
        abajo += 1
    return izquierda, arriba, derecha, abajo


def _generar_fondo_ventana(
    ancho: int,
    alto: int,
    tipo_cfg: ConfigTipo,
    variacion: int,
) -> Image.Image:
    """Crea el fondo degradado vertical con matiz atmosférico para la ventana."""
    fondo = Image.new("RGBA", (ancho, alto))
    draw = ImageDraw.Draw(fondo)

    # Pequeño desplazamiento cromático determinista por carta para que cada binario sea único
    delta = (variacion % 11) - 5

    def ajustar(c: tuple[int, int, int]) -> tuple[int, int, int]:
        return (
            max(0, min(255, c[0] + delta)),
            max(0, min(255, c[1] - delta)),
            max(0, min(255, c[2] + (delta // 2))),
        )

    sup = ajustar(tipo_cfg.color_superior)
    med = ajustar(tipo_cfg.color_medio)
    inf = ajustar(tipo_cfg.color_inferior)

    punto_medio = 0.55
    for y in range(alto):
        ratio = y / max(1, alto - 1)
        if ratio < punto_medio:
            u = ratio / punto_medio
            r = int(sup[0] * (1 - u) + med[0] * u)
            g = int(sup[1] * (1 - u) + med[1] * u)
            b = int(sup[2] * (1 - u) + med[2] * u)
        else:
            u = (ratio - punto_medio) / (1.0 - punto_medio)
            r = int(med[0] * (1 - u) + inf[0] * u)
            g = int(med[1] * (1 - u) + inf[1] * u)
            b = int(med[2] * (1 - u) + inf[2] * u)
        draw.line([(0, y), (ancho, y)], fill=(r, g, b, 255))

    return fondo


class EnsambladorCartas:
    """Ensambla en memoria las capas gráficas de una carta en proporción 5:7."""

    def __init__(self, assets_dir: Path = ASSETS_DIR) -> None:
        self._assets_dir = assets_dir
        self._marcos_cache: dict[str, tuple[Image.Image, tuple[int, int, int, int]]] = {}
        self._escudos_cache: dict[str, Image.Image] = {}

    def _obtener_marco(self, nombre_archivo: str) -> tuple[Image.Image, tuple[int, int, int, int]]:
        if nombre_archivo not in self._marcos_cache:
            ruta = self._assets_dir / "marco" / nombre_archivo
            with Image.open(ruta) as img:
                marco = img.convert("RGBA").resize(
                    (CARD_WIDTH, CARD_HEIGHT),
                    Image.Resampling.LANCZOS,
                )
            ventana = _detectar_ventana_transparente(marco)
            self._marcos_cache[nombre_archivo] = (marco, ventana)
        return self._marcos_cache[nombre_archivo]

    def _obtener_escudo(self, nombre_archivo: str) -> Image.Image:
        if nombre_archivo not in self._escudos_cache:
            ruta = self._assets_dir / "tipo" / nombre_archivo
            with Image.open(ruta) as img:
                escudo = img.convert("RGBA")
            bbox = escudo.getbbox()
            if bbox:
                escudo = escudo.crop(bbox)
            ancho_objetivo = int(CARD_WIDTH * 0.165)
            alto_objetivo = max(1, int(escudo.height * (ancho_objetivo / escudo.width)))
            self._escudos_cache[nombre_archivo] = escudo.resize(
                (ancho_objetivo, alto_objetivo),
                Image.Resampling.LANCZOS,
            )
        return self._escudos_cache[nombre_archivo]

    def ensamblar_png(
        self,
        tipo_cfg: ConfigTipo,
        rareza_cfg: ConfigRareza,
        ruta_sprite: Path,
        semilla_unica: int,
    ) -> bytes:
        """Superpone fondo + Pokémon + marco de rareza + escudo de tipo y devuelve bytes PNG."""
        marco, (izq, arr, der, aba) = self._obtener_marco(rareza_cfg.archivo_marco)
        escudo = self._obtener_escudo(tipo_cfg.archivo_escudo)

        # Expandimos ligeramente la ventana para que quede cubierta bajo el bisel del marco
        margen = 12
        wl = max(0, izq - margen)
        wt = max(0, arr - margen)
        wr = min(CARD_WIDTH, der + margen)
        wb = min(CARD_HEIGHT, aba + margen)
        ww, wh = wr - wl, wb - wt

        # 1. Capa de fondo degradado dentro de la ventana
        ventana_canvas = _generar_fondo_ventana(ww, wh, tipo_cfg, semilla_unica)

        # 2. Capa del Pokémon centrada y ajustada a la ventana
        with Image.open(ruta_sprite) as sprite_raw:
            sprite_raw.seek(0)
            sprite = sprite_raw.convert("RGBA")
        sbbox = sprite.getbbox()
        if sbbox:
            sprite = sprite.crop(sbbox)

        escala = min((ww * 0.95) / max(1, sprite.width), (wh * 0.98) / max(1, sprite.height))
        sw = max(1, int(sprite.width * escala))
        sh = max(1, int(sprite.height * escala))
        sprite_redimensionado = sprite.resize((sw, sh), Image.Resampling.LANCZOS)

        sx = (ww - sw) // 2
        sy = max(0, wh - sh + int(margen * 0.4))
        ventana_canvas.alpha_composite(sprite_redimensionado, (sx, sy))

        # 3. Lienzo 5:7 principal: ventana + marco superpuesto
        lienzo = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        lienzo.alpha_composite(ventana_canvas, (wl, wt))
        lienzo.alpha_composite(marco, (0, 0))

        # 4. Escudo de tipo elemental centrado en la barra superior de la ventana
        bx = (CARD_WIDTH - escudo.width) // 2
        by = arr - int(escudo.height * 0.55)
        lienzo.alpha_composite(escudo, (bx, max(0, by)))

        salida = BytesIO()
        lienzo.save(salida, format="PNG", compress_level=6)
        return salida.getvalue()


async def _sincronizar_proyeccion_mongo(total_esperado: int) -> int:
    """Sincroniza los eventos CardCreated pendientes hacia MongoDB cards_projection."""
    from src.database.mongodb.connection import get_mongo_db
    from src.modules.catalogo.catalogo_module import componer_procesador_outbox

    db = get_mongo_db(conexion_directa=True)
    # Asegurar que exista el índice único sobre `code` requerido por el proyector 1F
    await db["cards_projection"].create_index([("code", 1)], unique=True)

    procesador, almacen, _ = componer_procesador_outbox()
    await almacen.verificar_indices()

    detener = asyncio.Event()
    total_sincronizados = 0
    while True:
        lote = await procesador.lote(
            limite=max(50, total_esperado),
            concurrencia=4,
            detener=detener,
        )
        total_sincronizados += lote
        if lote == 0:
            break
    return total_sincronizados


async def generar_e_inyectar_cartas(
    cantidad: int,
    *,
    semilla: int | None = None,
    preview_dir: Path | None = None,
) -> int:
    """Genera e inyecta `cantidad` cartas en PostgreSQL, GridFS y cards_projection."""
    cargar_entorno_desarrollo()

    from src.database.mongodb.connection import close_mongo_connection
    from src.database.postgresql.connection import engine
    from src.modules.catalogo.catalogo_module import (
        aplicacion_cartas,
        crear_servicio_crear_carta,
        dominio_cartas,
        listar_habilidades,
    )

    rng = random.Random(semilla)
    ensamblador = EnsambladorCartas(ASSETS_DIR)

    # Inventariar sprites por tipo elemental
    sprites_por_tipo: dict[str, list[Path]] = {}
    for codigo_tipo, cfg_tipo in TIPOS_CONFIG.items():
        carpeta = ASSETS_DIR / cfg_tipo.carpeta_sprites
        archivos = sorted(
            p for p in carpeta.iterdir()
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        )
        if not archivos:
            raise RuntimeError(f"No se encontraron sprites en {carpeta}")
        rng.shuffle(archivos)
        sprites_por_tipo[codigo_tipo] = archivos

    if preview_dir is not None:
        preview_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print(f"  GENERADOR E INYECTOR DE CARTAS POKÉ-ARENA (N = {cantidad})")
    print("=" * 72)
    print(
        "  Distribución de probabilidad: "
        + ", ".join(f"{r.etiqueta}={int(r.probabilidad * 100)}%" for r in RAREZAS_CONFIG)
    )
    print(f"  Resolución de ensamblaje    : {CARD_WIDTH}x{CARD_HEIGHT} px (5:7 exacto)")
    print("-" * 72)

    try:
        # Consultar habilidades disponibles en la base de datos (fallback a HAB-000)
        try:
            habilidades_db = await listar_habilidades()
            codigos_habilidad = [codigo for codigo, _ in habilidades_db] or ["HAB-000"]
        except Exception:
            codigos_habilidad = ["HAB-000"]

        servicio = crear_servicio_crear_carta()
        actor = aplicacion_cartas.ActorCreacion(id="script-generador-cartas")

        tipos_claves = list(TIPOS_CONFIG.keys())
        cursores_sprites: dict[str, int] = {k: 0 for k in tipos_claves}
        conteo_rarezas: dict[str, int] = {r.codigo: 0 for r in RAREZAS_CONFIG}
        conteo_tipos: dict[str, int] = {k: 0 for k in tipos_claves}

        creadas = 0
        for indice in range(1, cantidad + 1):
            # Selección de tipo elemental y rareza según probabilidad matemática
            codigo_tipo = rng.choice(tipos_claves)
            cfg_tipo = TIPOS_CONFIG[codigo_tipo]
            cfg_rareza = sortear_rareza(rng)

            # Seleccionar animal/Pokémon de la carpeta correspondiente al tipo
            lista_sprites = sprites_por_tipo[codigo_tipo]
            pos = cursores_sprites[codigo_tipo] % len(lista_sprites)
            cursores_sprites[codigo_tipo] += 1
            ruta_sprite = lista_sprites[pos]

            nombre_carta = formatear_nombre_pokemon(ruta_sprite)
            costo = rng.randint(cfg_rareza.costo_min, cfg_rareza.costo_max)
            poder = rng.randint(cfg_rareza.poder_min, cfg_rareza.poder_max)
            habilidad = rng.choice(codigos_habilidad)

            # Ensamblar imagen 5:7 superponiendo fondo + Pokémon + marco + escudo de tipo
            bytes_png = await asyncio.to_thread(
                ensamblador.ensamblar_png,
                cfg_tipo,
                cfg_rareza,
                ruta_sprite,
                indice * 1000 + rng.randint(1, 999),
            )

            datos_carta = dominio_cartas.DatosCarta(
                nombre=nombre_carta,
                costo=costo,
                poder=poder,
                tipo=codigo_tipo,
                rareza=cfg_rareza.codigo,
                habilidad=habilidad,
            )
            clave_idempotencia = f"seed-card-{uuid4()}"
            solicitud = aplicacion_cartas.SolicitudCrearCarta(
                clave_idempotencia=clave_idempotencia,
                datos=datos_carta,
                original=bytes_png,
            )

            resultado = await servicio.ejecutar(actor, solicitud)
            creadas += 1
            conteo_rarezas[cfg_rareza.codigo] += 1
            conteo_tipos[codigo_tipo] += 1

            if preview_dir is not None:
                nombre_seguro = re.sub(r"[^\w\-]+", "_", nombre_carta)
                archivo_preview = preview_dir / f"{resultado.codigo}_{nombre_seguro}.png"
                archivo_preview.write_bytes(bytes_png)

            print(
                f"  [{indice:03d}/{cantidad:03d}] {resultado.codigo} | "
                f"{nombre_carta:<22} | Tipo: {cfg_tipo.etiqueta:<9} | "
                f"Rareza: {cfg_rareza.etiqueta:<10} | Costo: {costo:2d} | Poder: {poder:2d}"
            )

        # Sincronizar Outbox -> MongoDB cards_projection para disponibilidad inmediata en la web
        print("-" * 72)
        print("  Sincronizando eventos Outbox hacia MongoDB ('cards_projection')...")
        proyectadas = await _sincronizar_proyeccion_mongo(creadas)

        print("=" * 72)
        print(f"  ¡PROCESO COMPLETADO! {creadas} cartas inyectadas y {proyectadas} proyectadas.")
        print("  Resumen por rareza : " + ", ".join(f"{k}: {v}" for k, v in conteo_rarezas.items()))
        print("  Resumen por tipo   : " + ", ".join(f"{k}: {v}" for k, v in conteo_tipos.items()))
        print("=" * 72)
        return 0
    finally:
        await close_mongo_connection()
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ensambla e inyecta N cartas aleatorias en Poké-Arena."
    )
    parser.add_argument(
        "cantidad",
        nargs="?",
        type=int,
        default=CANTIDAD_CARTAS_DEFAULT,
        help=f"Cantidad N de cartas a generar (por defecto: {CANTIDAD_CARTAS_DEFAULT})",
    )
    parser.add_argument(
        "-n",
        "--count",
        dest="cantidad_flag",
        type=int,
        default=None,
        help="Alternativa por bandera para indicar la cantidad N de cartas",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla opcional para reproducibilidad del sorteo",
    )
    parser.add_argument(
        "--preview-dir",
        type=Path,
        default=None,
        help="Directorio opcional donde guardar también copia local de las imágenes ensambladas",
    )

    args = parser.parse_args()
    n = args.cantidad_flag if args.cantidad_flag is not None else args.cantidad
    if n < 1:
        print("[ERROR] La cantidad de cartas N debe ser un entero mayor o igual a 1.")
        return 1

    try:
        return asyncio.run(
            generar_e_inyectar_cartas(
                n,
                semilla=args.seed,
                preview_dir=args.preview_dir,
            )
        )
    except KeyboardInterrupt:
        print("\n[INFO] Operación cancelada por el usuario.")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Falló la generación de cartas: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

