# IA-6 — Miniaturas y operación local

Buscar Carta y su detalle cargan la miniatura con `GET /api/v1/content/cards/{card_id}/thumbnail`, usando el ID que ya devuelve Catálogo y el Bearer interno. PostgreSQL resuelve la referencia de una imagen `READY` y el adaptador existente recupera el WebP desde GridFS. La respuesta es binaria, con caché privada de cinco minutos y `Vary: Authorization`. Una carta histórica sin miniatura devuelve `404` y React muestra el placeholder.

## Procesos en macOS

Ejecutar desde la raíz del repositorio en Bash o Zsh. Los siguientes comandos cargan las credenciales privadas en memoria, sin imprimirlas. Usar un directorio de corte privado que contenga `outbox-worker.secret` con permisos `0600`. Para una sesión nueva, definir la función otra vez.

```bash
export IA6_CUT_DIR="$HOME/pokearena-backups/ia5b/corte-20261109T203829Z-ibwbb690"
umask 077

ia6_run() {
  backend/.venv/bin/python -B - "$1" <<'PY'
import os
import sys
from pathlib import Path
from urllib.parse import quote

from dotenv import dotenv_values
from pymongo.uri_parser import parse_uri
from sqlalchemy import URL, make_url

mode = sys.argv[1]
assert mode in {"api", "outbox"}
private = dotenv_values(".env")
settings = {**{k: v for k, v in private.items() if v is not None}, **os.environ}
pg = make_url(settings.get("CUT_APP_PG_URL") or settings["DATABASE_URL"])
assert pg.username == "poke_api_user" and pg.password
if mode == "api":
    media = parse_uri(settings.get("CUT_API_MONGO_URL") or settings["MONGO_URL"])
    user, password = media["username"], media["password"]
    assert user == "poke_api_mongo" and password
else:
    user = "poke_outbox_mongo"
    secret = Path(os.environ["IA6_CUT_DIR"]) / "outbox-worker.secret"
    assert not secret.is_symlink() and secret.stat().st_mode & 0o777 == 0o600
    password = secret.read_text().strip()
    assert password
    import subprocess
    existing = subprocess.run(
        ["pgrep", "-f", "[s]rc.database.outbox_worker$"], capture_output=True,
    )
    if existing.returncode != 1:
        raise SystemExit("Ya hay un worker activo o no se pudo verificar el estado de procesos.")

env = {
    **os.environ,
    "DATABASE_URL": URL.create("postgresql+asyncpg", "poke_api_user", pg.password,
        "127.0.0.1", 5432, "pokearena_db").render_as_string(hide_password=False),
    "MONGO_URL": f"mongodb://{user}:{quote(password, safe='')}@127.0.0.1:27017/"
                 "pokearena_catalog?authSource=pokearena_catalog&directConnection=true",
    "MONGO_DB": "pokearena_catalog",
    "MONGO_GRIDFS_BUCKET": "card_assets",
    "ENVIRONMENT": "development",
    "ORIGINAL_RUNTIME": mode,
    "ORIGINAL_MIGRATION_ENABLED": "false",
    "IDENTITY_LOCAL_ENABLED": "false",
    "DEBUG": "false",
}
if mode == "api":
    for key in ("GOOGLE_OAUTH_CLIENT_ID", "PLATFORM_ADMIN_GOOGLE_SUBJECTS", "PLATFORM_ADMIN_EMAILS"):
        env[key] = settings.get(key, "")
    args = ["uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000"]
else:
    env.update(OUTBOX_BATCH_SIZE="1", OUTBOX_CONCURRENCY="1", OUTBOX_POLL_SECONDS="3")
    args = ["src.database.outbox_worker"]
os.chdir("backend")
os.execve(sys.executable, [sys.executable, "-B", "-m", *args], env)
PY
}
```

FastAPI y React corren en terminales separadas. Confirmar primero que los puertos están libres. Vite carga su Client ID privado en modo de desarrollo.

```bash
ia6_run api
# En otra terminal desde la raíz:
(cd frontend && VITE_BACKEND_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173 --strictPort)
# Desde una tercera terminal:
curl -fsS http://127.0.0.1:5173/api/v1/health
```

Para detener FastAPI o React desde su terminal, usar Ctrl-C. Si están en segundo plano, identificar los listeners y comprobar que corresponden a Uvicorn y Vite antes de enviar SIGTERM.

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
IA6_API_PID=$(lsof -t -nP -iTCP:8000 -sTCP:LISTEN)
IA6_REACT_PID=$(lsof -t -nP -iTCP:5173 -sTCP:LISTEN)
ps -p "$IA6_API_PID,$IA6_REACT_PID" -o pid=,command=
# Tras confirmar los dos procesos:
kill -TERM "$IA6_API_PID" "$IA6_REACT_PID"
```

Antes de iniciar o reiniciar Outbox, aplicar el preflight del runbook de corte. Inspeccionar todos los eventos con la consulta siguiente y detenerse ante cualquier evento inesperado o cualquier otro worker activo.

```bash
docker exec pokearena-postgres sh -ec '
  export PGPASSWORD="$POSTGRES_PASSWORD" PGOPTIONS="-c default_transaction_read_only=on"
  exec psql -X -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d pokearena_db -v ON_ERROR_STOP=1
' <<'SQL'
SELECT version_num FROM alembic_version;
SELECT id,event_type,aggregate_type,status,attempts,next_attempt_at,lease_expires_at
FROM shared_outbox ORDER BY created_at,id;
SQL

pgrep -fl '[s]rc.database.outbox_worker$'
# Arrancar en una terminal dedicada cuando se haya aprobado la cola:
ia6_run outbox >> "$IA6_CUT_DIR/outbox-ia6-continuo.log" 2>&1
# Observar desde otra terminal:
tail -f "$IA6_CUT_DIR/outbox-ia6-continuo.log"
```

Para detenerlo, usar Ctrl-C en su terminal o identificar la instancia única y enviar SIGTERM. El worker termina el grupo activo antes de salir.

```bash
IA6_PID=$(pgrep -f '[s]rc.database.outbox_worker$')
case "$IA6_PID" in
  ''|*[!0-9]*) printf '%s\n' 'Se esperaba exactamente un PID. Revisar antes de detener.' ;;
  *) kill -TERM "$IA6_PID" ;;
esac
pgrep -fl '[s]rc.database.outbox_worker$'
```

Para reiniciar, esperar a que la última consulta ya no muestre el proceso, volver a verificar la cola y ejecutar el mismo comando de arranque. Esta ejecución local no registra un servicio de macOS.

## Aceptación desde el navegador

1. Iniciar sesión como administrador. Buscar `PKA-AGU-001` y comprobar su miniatura en el grid y el detalle. Buscar `PKA-PLA-001` y comprobar el placeholder.
2. Crear una carta con imagen desde el portal y guardar su código. Con Outbox activo, esperar su publicación y buscarla por código. Verificar su miniatura y los atributos.
3. Cerrar sesión e iniciar como jugador. Con menos de 15 cartas `COMUN` distintas con imagen `READY`, el estado esperado es `PENDING_CATALOG`. Para verificar entrega y apertura se requiere alcanzar ese mínimo mediante creaciones autorizadas.
4. Cuando el catálogo cumpla el mínimo, volver a ingresar con el jugador pendiente. Verificar 15 cartas distintas y 1.000 cubos, abrir el paquete y repetir el ingreso y la apertura. Comprobar que el inventario, el saldo y la fecha de apertura se conservan.
