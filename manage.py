#!/usr/bin/env python3
"""Script centralizado de gestión para Poké-Arena (CLI Cross-Platform).

Automatiza la instalación de dependencias, orquestación de Docker,
ejecución de pruebas y verificación de calidad tanto en Windows como en Linux/macOS.
Uso:
    python manage.py <comando>
"""

import argparse
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

# Asegurar codificación UTF-8 en Windows para evitar errores con caracteres especiales
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
IS_WINDOWS = platform.system() == "Windows"


def get_backend_python() -> Path:
    """Retorna la ruta al ejecutable de Python del entorno virtual."""
    if IS_WINDOWS:
        return BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return BACKEND_DIR / ".venv" / "bin" / "python"


def get_backend_pytest() -> Path:
    """Retorna la ruta al ejecutable de pytest del entorno virtual."""
    if IS_WINDOWS:
        return BACKEND_DIR / ".venv" / "Scripts" / "pytest.exe"
    return BACKEND_DIR / ".venv" / "bin" / "pytest"


def get_backend_ruff() -> Path:
    """Retorna la ruta a ruff del entorno virtual."""
    if IS_WINDOWS:
        return BACKEND_DIR / ".venv" / "Scripts" / "ruff.exe"
    return BACKEND_DIR / ".venv" / "bin" / "ruff"


def get_backend_mypy() -> Path:
    """Retorna la ruta a mypy del entorno virtual."""
    if IS_WINDOWS:
        return BACKEND_DIR / ".venv" / "Scripts" / "mypy.exe"
    return BACKEND_DIR / ".venv" / "bin" / "mypy"


def get_npm_cmd() -> str:
    """Retorna el comando para invocar npm según el sistema operativo."""
    return "npm.cmd" if IS_WINDOWS else "npm"


def run_cmd(cmd: list[str] | str, cwd: Path = ROOT_DIR, check: bool = True) -> int:
    """Ejecuta un comando en consola mostrando la salida en tiempo real."""
    cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else cmd
    print(f"\n[CLI] > {cmd_str} (en {cwd.relative_to(ROOT_DIR) if cwd != ROOT_DIR else '.'})")
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str))
    if check and res.returncode != 0:
        print(f"\n[ERROR] El comando falló con código {res.returncode}")
        sys.exit(res.returncode)
    return res.returncode


# ------------------------------------------------------------------------------
# COMANDOS DISPONIBLES
# ------------------------------------------------------------------------------


def cmd_install_deps(_args: argparse.Namespace) -> None:
    """Instala todas las dependencias del proyecto (Backend y Frontend)."""
    print("=" * 65)
    print("  INSTALANDO DEPENDENCIAS DE POKÉ-ARENA (BACKEND + FRONTEND)")
    print("=" * 65)

    # 1. Archivo .env
    env_file = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"
    if not env_file.exists() and env_example.exists():
        print("\n[1/3] Creando archivo .env a partir de .env.example...")
        shutil.copy(env_example, env_file)
        print("  -> Archivo .env creado con éxito.")
    else:
        print("\n[1/3] Archivo .env ya presente.")

    # 2. Backend virtualenv & dependencias
    print("\n[2/3] Configurando entorno virtual e instalando librerías de Python...")
    venv_dir = BACKEND_DIR / ".venv"
    if not venv_dir.exists():
        print("  -> Creando nuevo entorno virtual .venv en backend/...")
        run_cmd([sys.executable, "-m", "venv", ".venv"], cwd=BACKEND_DIR)

    python_bin = get_backend_python()
    if not python_bin.exists():
        print(f"[ERROR] No se encontró el ejecutable de Python en {python_bin}")
        sys.exit(1)

    print("  -> Instalando paquetes de backend (FastAPI, SQLAlchemy, Pytest, Ruff, Mypy)...")
    run_cmd([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=BACKEND_DIR)
    run_cmd([str(python_bin), "-m", "pip", "install", "-e", ".[dev]"], cwd=BACKEND_DIR)

    # 3. Frontend node modules
    print("\n[3/3] Instalando paquetes de Node.js en frontend/ (npm install)...")
    npm_cmd = get_npm_cmd()
    run_cmd([npm_cmd, "install"], cwd=FRONTEND_DIR)

    print("\n" + "=" * 65)
    print("  ¡INSTALACIÓN COMPLETADA CON ÉXITO!")
    print("  Ya puedes iniciar las bases de datos con: python manage.py start-dbs")
    print("  O levantar el sistema completo con:      python manage.py start-full")
    print("=" * 65)


def cmd_start_dbs(_args: argparse.Namespace) -> None:
    """Levanta ÚNICAMENTE las bases de datos en Docker (Modo desarrollo diario)."""
    print("\n[Docker] Levantando bases de datos (Postgres Master :5432, Réplica :5433, Mongo :27017)...")
    print("[Info] Ideal para programar en local con 'uvicorn' y 'npm run dev'.")
    run_cmd(["docker", "compose", "up", "-d"])


def cmd_start_full(_args: argparse.Namespace) -> None:
    """Levanta TODO el sistema en Docker (Bases de datos + 2 Backends + Frontend + Nginx)."""
    print("\n[Docker] Construyendo y levantando clúster completo (Full Stack Evaluation Mode)...")
    print("[Info] Servirá la aplicación en http://localhost (puerto 80).")
    run_cmd(["docker", "compose", "--profile", "full", "up", "-d", "--build"])
    print("\n[OK] Clúster encendido. Visita:")
    print("  -> Frontend:    http://localhost")
    print("  -> Healthcheck: http://localhost/api/v1/health")
    print("  -> Swagger:     http://localhost/docs")


def cmd_stop(_args: argparse.Namespace) -> None:
    """Detiene y apaga los contenedores conservando los datos guardados en las bases de datos."""
    print("\n[Docker] Deteniendo contenedores (conservando volúmenes de datos)...")
    run_cmd(["docker", "compose", "--profile", "full", "down"])
    print("[OK] Contenedores detenidos. Tus datos en Postgres y Mongo se conservan.")


def cmd_stop_clean(_args: argparse.Namespace) -> None:
    """Detiene los contenedores y BORRA los datos de las bases de datos (Reset total)."""
    print("\n[Docker] [ADVERTENCIA] Deteniendo contenedores y BORRANDO volúmenes persistentes...")
    run_cmd(["docker", "compose", "--profile", "full", "down", "-v"])
    print("[OK] Clúster detenido y volúmenes eliminados. Bases de datos limpias.")


def cmd_status(_args: argparse.Namespace) -> None:
    """Muestra el estado actual y puertos de todos los contenedores de Docker."""
    run_cmd(["docker", "compose", "--profile", "full", "ps"])


def cmd_logs(args: argparse.Namespace) -> None:
    """Muestra los logs en tiempo real de los contenedores."""
    service = [args.service] if args.service else []
    run_cmd(["docker", "compose", "logs", "-f"] + service)


def cmd_test(_args: argparse.Namespace) -> None:
    """Ejecuta las pruebas unitarias y de arquitectura con Pytest."""
    pytest_bin = get_backend_pytest()
    if not pytest_bin.exists():
        print(f"[ERROR] Pytest no encontrado en {pytest_bin}. Ejecuta primero: python manage.py install-deps")
        sys.exit(1)
    print("\n[Pytest] Ejecutando pruebas unitarias y de arquitectura...")
    run_cmd([str(pytest_bin), "tests/unit", "tests/architecture", "-v"], cwd=BACKEND_DIR)


def cmd_lint(_args: argparse.Namespace) -> None:
    """Ejecuta el linter (Ruff) y el verificador estático de tipos (Mypy)."""
    ruff_bin = get_backend_ruff()
    mypy_bin = get_backend_mypy()

    print("\n[1/2] Verificando estándares y estilo de código con Ruff...")
    run_cmd([str(ruff_bin), "check", "."], cwd=BACKEND_DIR)

    print("\n[2/2] Verificando tipado estricto con Mypy...")
    run_cmd([str(mypy_bin), "src/"], cwd=BACKEND_DIR)
    print("\n[OK] Código 100% conforme a los estándares de calidad.")


def cmd_smoke_test(_args: argparse.Namespace) -> None:
    """Ejecuta el Smoke Test de signos vitales contra el clúster activo."""
    python_bin = get_backend_python()
    script_content = """
import io, sys, uuid, httpx
from PIL import Image

BASE_URL = "http://localhost"
def img_bytes(w, h):
    im = Image.new("RGB", (w, h), (255, 68, 68))
    b = io.BytesIO(); im.save(b, format="JPEG"); return b.getvalue()

c = httpx.Client(base_url=BASE_URL, timeout=10.0)
print("[1/5] Frontend Web:", c.get("/").status_code)
print("[2/5] Swagger Docs:", c.get("/docs").status_code)
h = c.get("/api/v1/health").json()
print("[3/5] Healthcheck:", h.get("status"), h.get("databases"))
assert h.get("status") == "healthy"

uid = uuid.uuid4().hex[:6].upper()
card_res = c.post("/api/v1/content/cards", data={"code": f"CLI-{uid}", "name": f"Pikachu-{uid}", "cost": 3, "power": 50, "card_type": "ELE", "rarity": "COMUN", "ability_type": "HAB-000"}, files={"image": ("c.jpg", img_bytes(500, 700), "image/jpeg")})
print("[4/5] Crear Carta 5:7:", card_res.status_code, card_res.json().get("code"))
assert card_res.status_code == 201

srch = c.get(f"/api/v1/content/cards?name=Pikachu-{uid}").json()
print("[5/5] Buscar en MongoDB:", srch.get("total"), "encontrados")
assert srch.get("total") >= 1
print("\\n[SMOKE TEST OK] Todos los servicios responden correctamente.")
"""
    run_cmd([str(python_bin), "-c", script_content], cwd=ROOT_DIR)


# ------------------------------------------------------------------------------
# PARSER PRINCIPAL DE ARGUMENTOS
# ------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python manage.py",
        description="⚡ Poké-Arena CLI: Centralizador de Comandos de Desarrollo y Despliegue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python manage.py install-deps       # Instala dependencias de backend y frontend
  python manage.py start-dbs          # Levanta solo las bases de datos (Postgres y Mongo)
  python manage.py start-full         # Levanta el sistema completo (Frontend + Backends + Nginx)
  python manage.py stop               # Apaga los contenedores conservando los datos
  python manage.py stop-clean         # Apaga los contenedores y borra los datos (Reset)
  python manage.py test               # Corre pruebas unitarias y de arquitectura
  python manage.py lint               # Valida estilo con Ruff y tipos con Mypy
  python manage.py smoke-test         # Corre el Smoke Test de signos vitales
  python manage.py status             # Ver estado de los contenedores Docker
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # install-deps
    sub_install = subparsers.add_parser(
        "install-deps",
        aliases=["install"],
        help="Instala todas las dependencias (Backend .venv + pip y Frontend npm install)",
    )
    sub_install.set_defaults(func=cmd_install_deps)

    # start-dbs
    sub_dbs = subparsers.add_parser(
        "start-dbs",
        aliases=["dbs"],
        help="Levanta únicamente las bases de datos en Docker (Postgres Master, Réplica y Mongo)",
    )
    sub_dbs.set_defaults(func=cmd_start_dbs)

    # start-full
    sub_full = subparsers.add_parser(
        "start-full",
        aliases=["up"],
        help="Levanta todo el clúster (2 Backends + Frontend + Nginx + Bases de datos en :80)",
    )
    sub_full.set_defaults(func=cmd_start_full)

    # stop
    sub_stop = subparsers.add_parser(
        "stop",
        aliases=["down"],
        help="Detiene todos los contenedores Docker (conservando los datos de las bases de datos)",
    )
    sub_stop.set_defaults(func=cmd_stop)

    # stop-clean
    sub_clean = subparsers.add_parser(
        "stop-clean",
        aliases=["clean"],
        help="Detiene los contenedores y BORRA los datos de las bases de datos (Reset total)",
    )
    sub_clean.set_defaults(func=cmd_stop_clean)

    # status
    sub_status = subparsers.add_parser("status", help="Muestra el estado de los contenedores Docker")
    sub_status.set_defaults(func=cmd_status)

    # logs
    sub_logs = subparsers.add_parser("logs", help="Muestra los logs en tiempo real de Docker")
    sub_logs.add_argument("service", nargs="?", help="Nombre del servicio específico (ej. backend-1)")
    sub_logs.set_defaults(func=cmd_logs)

    # test
    sub_test = subparsers.add_parser(
        "test",
        aliases=["run-tests"],
        help="Ejecuta la suite de pruebas automatizadas (unitarias y arquitectura con Pytest)",
    )
    sub_test.set_defaults(func=cmd_test)

    # lint
    sub_lint = subparsers.add_parser(
        "lint",
        aliases=["run-lint"],
        help="Ejecuta el linter (Ruff) y el verificador estricto de tipos (Mypy)",
    )
    sub_lint.set_defaults(func=cmd_lint)

    # smoke-test
    sub_smoke = subparsers.add_parser(
        "smoke-test",
        aliases=["smoke"],
        help="Ejecuta la prueba de humo de signos vitales contra el sistema en vivo",
    )
    sub_smoke.set_defaults(func=cmd_smoke_test)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
