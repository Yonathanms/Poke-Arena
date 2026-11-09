#!/usr/bin/env python3
"""Script de gestión y desarrollo local para Poké-Arena.

Uso:
    python manage.py <comando>
"""

import argparse
import io
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

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

_DEV_SQL_GRANTS = """
GRANT USAGE ON SCHEMA public TO orm_media_test;
GRANT SELECT ON alembic_version, catalog_abilities TO orm_media_test;
GRANT SELECT, UPDATE ON catalog_card_code_counters TO orm_media_test;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  catalog_cards, catalog_card_images, shared_idempotency_records,
  shared_outbox, identity_sessions,
  locations, outbox_events, idempotency_records
TO orm_media_test;
REVOKE UPDATE, DELETE, TRUNCATE ON public.identity_users FROM orm_media_test;
REVOKE UPDATE (id, provider, provider_subject, role, created_at, local_password_hash)
ON public.identity_users FROM orm_media_test;
GRANT SELECT, INSERT ON public.identity_users TO orm_media_test;
GRANT UPDATE (email, updated_at, local_failed_attempts, local_blocked_until)
ON public.identity_users TO orm_media_test;
REVOKE UPDATE, DELETE ON public.player_profiles, public.player_cards, public.cube_transactions
FROM orm_media_test;
GRANT SELECT, INSERT ON public.player_profiles, public.player_cards, public.cube_transactions
TO orm_media_test;
GRANT UPDATE (cubes, has_received_initial_collection, updated_at) ON public.player_profiles
TO orm_media_test;
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'poke_api_user') THEN
    GRANT USAGE ON SCHEMA public TO poke_api_user;
    GRANT SELECT ON alembic_version, catalog_abilities TO poke_api_user;
    GRANT SELECT, UPDATE ON catalog_card_code_counters TO poke_api_user;
    GRANT SELECT, INSERT, UPDATE, DELETE ON
      catalog_cards, catalog_card_images, shared_idempotency_records,
      shared_outbox, identity_sessions,
      locations, outbox_events, idempotency_records
    TO poke_api_user;
    REVOKE UPDATE, DELETE, TRUNCATE ON public.identity_users FROM poke_api_user;
    REVOKE UPDATE (id, provider, provider_subject, role, created_at, local_password_hash)
    ON public.identity_users FROM poke_api_user;
    GRANT SELECT, INSERT ON public.identity_users TO poke_api_user;
    GRANT UPDATE (email, updated_at, local_failed_attempts, local_blocked_until)
    ON public.identity_users TO poke_api_user;
    REVOKE UPDATE, DELETE ON public.player_profiles, public.player_cards, public.cube_transactions
    FROM poke_api_user;
    GRANT SELECT, INSERT ON public.player_profiles, public.player_cards, public.cube_transactions
    TO poke_api_user;
    GRANT UPDATE (cubes, has_received_initial_collection, updated_at) ON public.player_profiles
    TO poke_api_user;
  END IF;
  IF EXISTS (
    SELECT FROM pg_attribute
    WHERE attrelid = 'public.player_profiles'::regclass
      AND attname = 'initial_pack_opened_at' AND NOT attisdropped
  ) THEN
    GRANT UPDATE (initial_pack_opened_at) ON public.player_profiles TO orm_media_test;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'poke_api_user') THEN
      GRANT UPDATE (initial_pack_opened_at) ON public.player_profiles TO poke_api_user;
    END IF;
  END IF;
END $$;
"""


def get_backend_python() -> Path:
    """Ruta al Python del entorno virtual."""
    if IS_WINDOWS:
        return BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return BACKEND_DIR / ".venv" / "bin" / "python"


def run_cmd(cmd: list[str] | str, cwd: Path = ROOT_DIR, env: dict[str, str] | None = None) -> int:
    """Ejecuta un comando en consola mostrando la salida en tiempo real."""
    cmd_str = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else cmd
    print(f"\n[CLI] > {cmd_str}")
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), env=cmd_env)
    if res.returncode != 0:
        print(f"\n[ERROR] El comando falló con código {res.returncode}")
        sys.exit(res.returncode)
    return res.returncode


def run_quiet(cmd: list[str], input_data: str | None = None) -> tuple[int, str, str]:
    """Ejecuta un comando capturando salida sin detener el script ante error."""
    res = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        input=input_data.encode("utf-8") if input_data else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = res.stdout.decode("utf-8", errors="replace")
    stderr = res.stderr.decode("utf-8", errors="replace")
    return res.returncode, stdout, stderr


def _aplicar_permisos_desarrollo() -> None:
    """Aplica los permisos en una transacción y detiene el CLI ante un error."""
    code, _, _ = run_quiet(
        [
            "docker", "exec", "-i", "pokearena-postgres",
            "psql", "-X", "-v", "ON_ERROR_STOP=1", "--single-transaction",
            "-U", "postgres", "-d", "pokearena_alembic_frontend_dev", "-f", "-",
        ],
        input_data=_DEV_SQL_GRANTS,
    )
    if code != 0:
        raise SystemExit("No se pudieron aplicar los permisos de desarrollo.")


# ------------------------------------------------------------------------------
# COMANDOS PRINCIPALES
# ------------------------------------------------------------------------------


def cmd_setup_env(_args: argparse.Namespace) -> None:
    """Copia .env.example a .env si no existe o asegura variables mínimas de desarrollo."""
    env_file = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        if not IS_WINDOWS:
            env_file.chmod(0o600)
        print("\n[OK] Archivo .env generado exitosamente a partir de .env.example.")
    elif env_file.exists():
        print("\n[INFO] El archivo .env ya existe.")
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
    print("  ¡LISTO! Ya puedes iniciar y aprovisionar las bases de datos con:")
    print("  python manage.py setup-dev")
    print("=" * 60)


def ensure_docker_prerequisites() -> None:
    """Verifica y crea la red y volúmenes requeridos por docker-compose.yml si no existen."""
    # Red poke-arena_default
    code, stdout, _ = run_quiet(["docker", "network", "ls", "--format", "{{.Name}}"])
    if code == 0 and "poke-arena_default" not in stdout.splitlines():
        print("[Docker] Creando red externa 'poke-arena_default'...")
        run_quiet(["docker", "network", "create", "poke-arena_default"])

    # Volúmenes externos
    code, stdout, _ = run_quiet(["docker", "volume", "ls", "--format", "{{.Name}}"])
    if code == 0:
        existing_vols = set(stdout.splitlines())
        for vol in ["pokearena_pgmaster_data", "pokearena_mongo_data", "pokearena_mongo_config_data"]:
            if vol not in existing_vols:
                print(f"[Docker] Creando volumen persistente '{vol}'...")
                run_quiet(["docker", "volume", "create", vol])


def cmd_dbs(_args: argparse.Namespace) -> None:
    """Inicia PostgreSQL 16 y MongoDB 7 en Docker asegurando prerrequisitos de red y volumen."""
    ensure_docker_prerequisites()
    print("\n[Docker] Iniciando PostgreSQL (:5432) y MongoDB (:27017)...")
    run_cmd(["docker", "compose", "up", "-d", "--no-recreate"])


def cmd_setup_dev(args: argparse.Namespace) -> None:
    """Aprovisiona automáticamente PostgreSQL, MongoDB, migraciones Alembic y el administrador local."""
    print("=" * 60)
    print("  APROVISIONAMIENTO DE DESARROLLO (POSTGRES + MONGO + ALEMBIC)")
    print("=" * 60)

    # 1. Iniciar Docker si no está corriendo
    cmd_dbs(args)

    # 2. Esperar a que PostgreSQL esté receptivo
    print("\n[1/5] Esperando a que PostgreSQL esté listo...")
    for _ in range(15):
        code, _, _ = run_quiet(["docker", "exec", "pokearena-postgres", "pg_isready", "-U", "postgres"])
        if code == 0:
            break
        time.sleep(1)

    # 3. Crear roles de base de datos y la base de datos de desarrollo
    print("\n[2/5] Creando roles y base de datos 'pokearena_alembic_frontend_dev'...")
    sql_init = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'pokearena_migrator') THEN
    CREATE ROLE pokearena_migrator LOGIN PASSWORD 'migrator_pass_2026';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'orm_media_test') THEN
    CREATE ROLE orm_media_test LOGIN PASSWORD 'app_pass_2026';
  END IF;
END $$;
SELECT 'CREATE DATABASE pokearena_alembic_frontend_dev OWNER pokearena_migrator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'pokearena_alembic_frontend_dev')\\gexec
"""
    code, stdout, stderr = run_quiet(["docker", "exec", "-i", "pokearena-postgres", "psql", "-U", "postgres", "-d", "postgres"], input_data=sql_init)
    if code != 0:
        print(f"[ERROR] No se pudo inicializar roles en PostgreSQL: {stderr}")
        sys.exit(1)

    # 4. Ejecutar migraciones Alembic
    print("\n[3/5] Aplicando migraciones históricas y sucesoras con Alembic...")
    py = get_backend_python()
    migration_env = {
        "MIGRATION_DATABASE_URL": "postgresql+asyncpg://pokearena_migrator:migrator_pass_2026@127.0.0.1:5432/pokearena_alembic_frontend_dev"
    }
    run_cmd([str(py), "-m", "alembic", "-c", "alembic.ini", "upgrade", "heads"], cwd=BACKEND_DIR, env=migration_env)

    # 5. Otorgar permisos a orm_media_test y poke_api_user
    print("\n[4/5] Otorgando permisos de tablas a los usuarios de aplicación...")
    _aplicar_permisos_desarrollo()

    # 6. Configurar índice único de MongoDB
    print("\n[5/5] Configurando colecciones e índices en MongoDB...")
    mongo_cmd = """
db.getSiblingDB('pokearena_catalog_frontend_dev').cards_projection.createIndex({ code: 1 }, { unique: true });
db.getSiblingDB('pokearena_catalog').cards_projection.createIndex({ code: 1 }, { unique: true });
"""
    run_quiet([
        "docker", "exec", "-i", "pokearena-mongo",
        "mongosh", "--quiet", "-u", "mongoadmin", "-p", "mongo_secure_pass_2026",
        "--authenticationDatabase", "admin"
    ], input_data=mongo_cmd)

    # 7. Aprovisionar administrador local
    password = getattr(args, "admin_password", None) or "PokeArenaMaster2026!"
    print("\n[Auth] Aprovisionando administrador local ('maestro-local')...")
    provision_code = f"""
import asyncio
from src.modules.identidad.identidad_module import provisionar_administrador
uid = asyncio.run(provisionar_administrador('maestro-local', '{password}'))
print('ID de usuario asignado:', uid)
"""
    prov_env = {
        "DATABASE_URL": "postgresql+asyncpg://orm_media_test:app_pass_2026@localhost:5432/pokearena_alembic_frontend_dev",
        "IDENTITY_LOCAL_ENABLED": "true"
    }
    run_cmd([str(py), "-c", provision_code], cwd=BACKEND_DIR, env=prov_env)

    print("\n" + "=" * 60)
    print("  ¡ENTORNO DE DESARROLLO LOCAL COMPLETAMENTE LISTO!")
    print("=" * 60)
    print("  • Base de datos SQL : PostgreSQL 16 (:5432) -> pokearena_alembic_frontend_dev")
    print("  • Base de datos NoSQL: MongoDB 7 (:27017) -> pokearena_catalog_frontend_dev")
    print("  • Administrador Web : maestro-local")
    print(f"  • Contraseña Admin  : {password}")
    print("\n  Para iniciar el proyecto en dos terminales:")
    print("    Terminal 1 (Backend) : cd backend && .venv\\Scripts\\activate && uvicorn src.main:app --reload")
    print("    Terminal 2 (Frontend): cd frontend && npm run dev")
    print("=" * 60)


def cmd_migrate(_args: argparse.Namespace) -> None:
    """Aplica las migraciones pendientes con Alembic y actualiza permisos en PostgreSQL."""
    print("=" * 60)
    print("  APLICANDO MIGRACIONES DE ESQUEMA CON ALEMBIC")
    print("=" * 60)
    ensure_docker_prerequisites()
    py = get_backend_python()
    migration_env = {
        "MIGRATION_DATABASE_URL": "postgresql+asyncpg://pokearena_migrator:migrator_pass_2026@127.0.0.1:5432/pokearena_alembic_frontend_dev"
    }
    print("\n[Alembic] Ejecutando 'alembic upgrade heads'...")
    run_cmd([str(py), "-m", "alembic", "-c", "alembic.ini", "upgrade", "heads"], cwd=BACKEND_DIR, env=migration_env)

    print("\n[PostgreSQL] Actualizando permisos de tablas para usuarios de aplicación...")
    _aplicar_permisos_desarrollo()
    print("\n[OK] Migraciones aplicadas y permisos actualizados exitosamente.")


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
        description="Poké-Arena CLI: Gestión de desarrollo local multiplataforma",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandos habituales:
  python manage.py install       # Configura .env e instala dependencias (Python + Node.js)
  python manage.py setup-dev     # Inicia Docker, corre Alembic, configura usuarios e indexa Mongo
  python manage.py migrate       # Aplica migraciones pendientes con Alembic y actualiza permisos
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
    
    sub_setup = sub.add_parser("setup-dev", aliases=["init-db", "provision"], help="Aprovisiona PostgreSQL, Alembic, MongoDB y admin local")
    sub_setup.add_argument("--password", dest="admin_password", default="PokeArenaMaster2026!", help="Contraseña para el usuario maestro-local")
    sub_setup.set_defaults(func=cmd_setup_dev)

    sub.add_parser("migrate", aliases=["alembic", "db-upgrade"], help="Aplica migraciones pendientes con Alembic").set_defaults(func=cmd_migrate)

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
