#!/usr/bin/env python3
"""Script de gestión y desarrollo local para Poké-Arena.

Uso:
    python manage.py <comando>
"""

import argparse
import io
from pathlib import Path
import platform
import shutil
import subprocess
import sys

# Asegurar codificación UTF-8 en terminales Windows
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
    """Ruta al Python del entorno virtual."""
    if IS_WINDOWS:
        return BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return BACKEND_DIR / ".venv" / "bin" / "python"


def run_cmd(cmd: list[str] | str, cwd: Path = ROOT_DIR) -> int:
    """Ejecuta un comando en consola mostrando la salida en tiempo real."""
    cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else cmd
    print(f"\n[CLI] > {cmd_str}")
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str))
    if res.returncode != 0:
        print(f"\n[ERROR] El comando falló con código {res.returncode}")
        sys.exit(res.returncode)
    return res.returncode


# ------------------------------------------------------------------------------
# COMANDOS PRINCIPALES
# ------------------------------------------------------------------------------


def cmd_setup_env(_args: argparse.Namespace) -> None:
    """Copia .env.example a .env si no existe."""
    env_file = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        if not IS_WINDOWS:
            env_file.chmod(0o600)
        print("\n[OK] Archivo .env generado exitosamente a partir de .env.example.")
    elif env_file.exists():
        print("\n[INFO] El archivo .env ya existe. No se sobrescribió.")
    else:
        print("\n[ERROR] No se encontró el archivo .env.example en la raíz.")


def cmd_install(_args: argparse.Namespace) -> None:
    """Instala dependencias de backend y frontend."""
    print("=" * 60)
    print("  INSTALANDO DEPENDENCIAS DE POKÉ-ARENA")
    print("=" * 60)

    # 1. Archivo .env
    cmd_setup_env(_args)

    # 2. Virtualenv y paquetes Python
    print("\n[2/3] Configurando entorno virtual e instalando Python...")
    venv_dir = BACKEND_DIR / ".venv"
    if not venv_dir.exists():
        run_cmd([sys.executable, "-m", "venv", ".venv"], cwd=BACKEND_DIR)

    py = get_backend_python()
    run_cmd([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=BACKEND_DIR)
    run_cmd([str(py), "-m", "pip", "install", "-e", ".[dev]"], cwd=BACKEND_DIR)

    # 3. Node modules
    print("\n[3/3] Instalando dependencias de React (npm install)...")
    npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
    run_cmd([npm_cmd, "install"], cwd=FRONTEND_DIR)

    print("\n" + "=" * 60)
    print("  ¡LISTO! Ya puedes iniciar las bases de datos con:")
    print("  python manage.py dbs")
    print("=" * 60)


def cmd_dbs(_args: argparse.Namespace) -> None:
    """Inicia servicios sin recrear contenedores existentes ni aplicar cambios pendientes.

    Compose verifica los recursos externos. Una recreación requiere revisar
    dependencias, respaldo y autorización; este atajo no la ejecuta.
    """
    print("\n[Docker] Iniciando PostgreSQL (:5432) y MongoDB (:27017)...")
    run_cmd(["docker", "compose", "up", "-d", "--no-recreate"])


def cmd_stop(_args: argparse.Namespace) -> None:
    """Detiene los contenedores conservando la data."""
    print("\n[Docker] Deteniendo bases de datos...")
    run_cmd(["docker", "compose", "down"])


def cmd_clean(_args: argparse.Namespace) -> None:
    """Detiene los contenedores y BORRA los datos (Reset de bases de datos)."""
    print("\n[Docker] [RESET] Borrando contenedores y volúmenes de datos...")
    run_cmd(["docker", "compose", "down", "-v"])


def cmd_status(_args: argparse.Namespace) -> None:
    """Muestra el estado de los contenedores."""
    run_cmd(["docker", "compose", "ps"])


def cmd_dev_backend(_args: argparse.Namespace) -> None:
    """Inicia el servidor FastAPI en local con recarga en vivo (:8000)."""
    py = get_backend_python()
    print("\n[Backend] Iniciando FastAPI en http://localhost:8000 (Swagger: /docs)...")
    run_cmd([str(py), "-m", "uvicorn", "src.main:app", "--reload", "--port", "8000"], cwd=BACKEND_DIR)


def cmd_dev_frontend(_args: argparse.Namespace) -> None:
    """Inicia el servidor frontend con Vite en local (:5173)."""
    npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
    print("\n[Frontend] Iniciando Vite en http://localhost:5173...")
    run_cmd([npm_cmd, "run", "dev"], cwd=FRONTEND_DIR)


def cmd_lint(_args: argparse.Namespace) -> None:
    """Valida estilo y tipos del backend con la configuración oficial."""
    py = get_backend_python()

    print("\n[1/2] Verificando con Ruff...")
    run_cmd([str(py), "-m", "ruff", "check", "src"], cwd=BACKEND_DIR)

    print("\n[2/2] Verificando con Mypy...")
    # El descubrimiento por rutas de Mypy corta el nombre al encontrar un guion.
    # Pasar los nombres completos conserva el contexto de los imports relativos.
    modules = []
    for path in sorted((BACKEND_DIR / "src").rglob("*.py")):
        name = ".".join(path.relative_to(BACKEND_DIR).with_suffix("").parts)
        modules.extend(("-m", name.removesuffix(".__init__")))
    run_cmd([str(py), "-m", "mypy", "--config-file", "pyproject.toml", *modules], cwd=BACKEND_DIR)
    print("\n[OK] Ruff y Mypy aprobaron el código del backend.")


def cmd_test(_args: argparse.Namespace) -> None:
    """Ejecuta la suite de pruebas automatizadas con Pytest."""
    py = get_backend_python()
    print("\n[Pytest] Ejecutando pruebas...")
    run_cmd([str(py), "-m", "pytest", "tests", "-v"], cwd=BACKEND_DIR)


# ------------------------------------------------------------------------------
# PARSER DE COMANDOS
# ------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python manage.py",
        description="Poké-Arena CLI: Gestión de desarrollo local",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandos habituales:
  python manage.py install       # Configura .env e instala dependencias (Python + Node.js)
  python manage.py env           # Genera .env a partir de .env.example
  python manage.py dbs           # Inicia Postgres y MongoDB en Docker
  python manage.py dev-backend   # Corre la API FastAPI en local (:8000)
  python manage.py dev-frontend  # Corre React / Vite en local (:5173)
  python manage.py lint          # Revisa estilo y tipos (Ruff + Mypy)
  python manage.py stop          # Detiene las bases de datos
  python manage.py clean         # Detiene y borra los datos de las bases de datos
        """,
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("install", aliases=["install-deps"], help="Instala dependencias y configura .env").set_defaults(func=cmd_install)
    sub.add_parser("env", aliases=["setup-env"], help="Genera archivo .env a partir de .env.example").set_defaults(func=cmd_setup_env)
    sub.add_parser("dbs", aliases=["start-dbs", "up"], help="Inicia bases de datos en Docker").set_defaults(func=cmd_dbs)
    sub.add_parser("stop", aliases=["down"], help="Detiene bases de datos").set_defaults(func=cmd_stop)
    sub.add_parser("clean", aliases=["stop-clean"], help="Detiene y borra bases de datos").set_defaults(func=cmd_clean)
    sub.add_parser("status", aliases=["ps"], help="Estado de contenedores").set_defaults(func=cmd_status)
    sub.add_parser("dev-backend", aliases=["backend", "api"], help="Corre FastAPI local").set_defaults(func=cmd_dev_backend)
    sub.add_parser("dev-frontend", aliases=["frontend", "front"], help="Corre Vite local").set_defaults(func=cmd_dev_frontend)
    sub.add_parser("lint", help="Corre Ruff y Mypy").set_defaults(func=cmd_lint)
    sub.add_parser("test", help="Corre Pytest").set_defaults(func=cmd_test)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
