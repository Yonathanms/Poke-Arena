# Entrega 1G — Cierre del backend Crear Carta

**Dictamen de cierre** — APROBADO CON OBSERVACIONES para el entorno aislado.
La API, la autenticación local y el worker se validaron juntos. El
aprovisionamiento y la configuración actuales siguen limitados a entornos
aislados. El despliegue original y Google real requieren autorización y
validación independientes.

## Estado integrado

| Fase | Componente reutilizado | Garantía y límite |
| --- | --- | --- |
| 1A | Configuración central, conexiones PostgreSQL 16 y MongoDB 7, Compose y roles técnicos. | El backend usa las fábricas oficiales. La preparación original no incluye la migración ni los permisos nuevos. |
| 1B | Alembic 001–008, sucesora 1B.2B, ORM y repositorio. | Se conserva la cadena, el esquema de catálogo y los datos. 1G amplía el CHECK de proveedor y añade columnas e índice de identidad. |
| 1C | Pillow y GridFS Async. | Se verifica original, WebP 200 × 280 y metadatos, sin modificar el adaptador. |
| 1D | Caso de uso, reserva, locks de clave y contador, idempotencia y evento. | Las revisiones 1B.2B y 1G tienen el mismo esquema de catálogo. |
| 1E | FastAPI, errores RFC 7807, Bearer, CORS y abstracción de sesiones. | Se añade un proveedor local explícito y revocación. Google queda disponible para una fase posterior. |
| 1F | Worker, leases, reintentos y proyección monotónica. | El worker admite la revisión 1G y continúa fuera de FastAPI. La proyección histórica requiere la conciliación de 1F. |
| 1G | Administrador único, lectura de habilidades, ensayo HTTP real y contrato para React. | El recorrido se verificó sin llamadas a Google ni cambios en las bases originales. |

```mermaid
flowchart LR
    A[Administrador local] --> I[Identidad y sesión opaca]
    I --> H[FastAPI y autorización]
    H --> C[Crear Carta 1D]
    C --> G[(MongoDB GridFS)]
    C --> P[(PostgreSQL)]
    P --> O[shared_outbox]
    O --> W[Worker 1F]
    W --> M[(cards_projection)]
```

El [contrato para React](CARD_CREATION_FRONTEND_HANDOFF.md) describe el
login, listado de habilidades, creación, idempotencia y errores. Los
detalles de [imágenes](GRIDFS_IMAGE_STORAGE_1C.md),
[transacciones](CARD_CREATION_SERVICE_1D.md) y
[recuperación del worker](CARD_CREATION_OUTBOX_1F.md) conservan sus
respectivos contratos.

## Identidad, sesión y esquema

La revisión 006 permite `GOOGLE` y `TEST`. `TEST` identifica cuentas de
ensayo históricas y no representa credenciales humanas verificadas.
Reutilizar ese valor o simular un sujeto Google mezclaría proveedores.
Un hash en configuración sin estado durable también dificultaría proteger
una única cuenta entre procesos. La sucesora `1g_local_master_admin`
incorpora `LOCAL`, tres columnas de credencial y limitación en
`identity_users` y un índice parcial que permite un solo maestro. Conserva
usuarios y sesiones preexistentes. El downgrade se niega si existe una
identidad LOCAL. Con la tabla sin identidades LOCAL se ensayó el ciclo
upgrade/downgrade/upgrade preservando usuarios GOOGLE y TEST.

El comando de aprovisionamiento solicita una contraseña de 16 a 256
caracteres en terminal sin eco y genera una sal aleatoria. Guarda un
hash scrypt con N=2¹⁷, r=8 y p=1. Un segundo aprovisionamiento para el
mismo usuario preserva la credencial original y la identidad SQL. Otro
identificador no puede ocupar el índice único. No hay aprovisionamiento
durante el arranque ni mediante una solicitud pública.
[OWASP, almacenamiento de contraseñas](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

El login verifica la contraseña bajo un lock de fila en PostgreSQL. Los
usuarios desconocidos consumen el mismo presupuesto que un intento
incorrecto contra la cuenta, con la misma respuesta 401. Cinco fallos
acumulados bloquean nuevos intentos por 60 segundos. Durante ese período,
la API devuelve 429 con `Retry-After`. El bloqueo evita carreras entre
procesos y sobrevive reinicios. Una verificación simultánea que no puede
adquirir el lock recibe 429 con espera breve. Un atacante con acceso a la
ruta puede provocar el bloqueo temporal de la única cuenta. Este diseño
es para aislamiento. Una exposición pública requeriría una revisión
separada de mitigación de abuso, operación y rotación.

El servicio común conserva el token opaco de 32 bytes aleatorios, su
SHA-256 en `identity_sessions`, expiración y revocación. La autorización
consulta el rol SQL en cada solicitud. Para GOOGLE se conserva además
la allowlist. Las sesiones TEST quedan excluidas. El catálogo recibe
el ID SQL autorizado y carece de dependencias de proveedores. Un futuro
adaptador de identidad se conecta a la composición de identidad y
reutiliza el servicio de sesiones.

`IDENTITY_LOCAL_ENABLED` vale `false` por defecto. Para habilitarlo se
exigen `ENVIRONMENT=development` o `test`, PostgreSQL en loopback con
nombre `pokearena_alembic_*` y la revisión 1G. El adaptador comprueba
destino y rol no superusuario antes de escribir. Para HTTP sin TLS, el
peer debe ser loopback. El ensayo se ejecuta con Uvicorn ligado a
`127.0.0.1` y sin interpretar headers de proxy.

## Archivos y validación

| Archivo o módulo | Cambio |
| --- | --- |
| `alembic/versions/010_local_master_admin.py` | Sucesora de 1B.2B, singleton y política de downgrade. |
| `database/postgresql/revisiones.py` | Revisiones compatibles compartidas por identidad, creación y Outbox. |
| `modules/identidad/identidad_module.py`, `gestion-sesiones/` | CLI, scrypt, rate limit SQL, revocación y endpoint local, reutilizando el servicio común. |
| `modules/catalogo/catalogo_module.py`, repositorio y controladores oficiales | Lectura mínima de habilidades existentes y compatibilidad con 1G. |
| `main.py`, `shared/config.py`, `.env.example` | CORS para revocación y opt-in de aislamiento. |
| `tests/test_backend_final_1g.py`, `test_alembic_recovery.py` | Aceptación HTTP y contrato de cadena Alembic. |
| `README.md`, `AGENTS.md`, contrato principal e informes 1G | Fase, operación, límites y entrega para React. |

Las 219 regresiones abarcan fallos parciales, validación de negocio, CORS,
competencia de contadores y Outbox, y commits inciertos. Los tres casos
nuevos cubren guard de configuración, scrypt y aceptación con Uvicorn
sobre un socket loopback. El ensayo integral aprovisiona dos veces sin
rotar el hash, rechaza una sesión TEST, comprueba que el bloqueo de login
sobrevive a Uvicorn, verifica el rol, expiración y revocación, hace un
replay HTTP y lee las filas y los binarios. Verifica la publicación con
el worker independiente arrancado después del 201. El rechazo del
downgrade con el maestro presente se prueba contra PostgreSQL.

| Control final | Resultado |
| --- | --- |
| Suite completa, PostgreSQL 16.15 y MongoDB 7.0.45 | **222 aprobadas, 0 fallidas, 0 omitidas**. |
| Archivo 1G sin URLs de integración | 2 aprobadas y 1 omitida por infraestructura. |
| Calidad | Ruff, Mypy de 44 módulos y el archivo nuevo de pruebas, compilación Python y `git diff --check` aprobados. |

La suite usó un PostgreSQL y dos MongoDB efímeros. El caso de aceptación
llamó al mismo aprovisionador de la CLI con una entrada privada de prueba.
El procedimiento manual usa el prompt interactivo y motores nuevos desde
cero.

```bash
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -p no:cacheprovider backend/tests -q -rs
backend/.venv/bin/python manage.py lint
backend/.venv/bin/python -m ruff check backend/tests/test_backend_final_1g.py backend/tests/test_alembic_recovery.py backend/alembic/versions/010_local_master_admin.py
(cd backend && .venv/bin/python -m mypy --config-file pyproject.toml -m tests.test_backend_final_1g)
backend/.venv/bin/python -m compileall -q backend/src backend/tests
git diff --check
```

La suite usa las URLs de regresión de [1F](CARD_CREATION_OUTBOX_1F.md) y
cuatro destinos privados para 1G: `IDENTITY_LOCAL_TEST_DATABASE_URL` y
`IDENTITY_LOCAL_TEST_MIGRATION_URL` hacia `pokearena_alembic_1g_master`,
`IDENTITY_LOCAL_TEST_MONGO_URL` y `IDENTITY_LOCAL_TEST_PROJECTION_URL`
hacia la misma base Mongo dedicada a 1G. Los roles que comprueba el test
son `orm_media_test`, `pokearena_migrator`, `media_test` y
`projection_test`. Preparar datos nuevos por ensayo. Usar una base Mongo
distinta de la que acompaña las regresiones, para evitar reutilizar códigos
entre copias SQL independientes. Las regresiones 1E usan claves RSA locales
y no hacen peticiones a Google.

## Inventario original y plan de despliegue

La auditoría en transacción de solo lectura encontró `pokearena_db` en
`008_flex_card_img_dims`, proveedores GOOGLE y TEST y cero filas que
incumplan cada uno de los dos nuevos CHECK de imágenes de 1B.2B. Es un
resultado puntual. Repetir el inventario en la ventana autorizada y
contrastar referencias físicas, índices y documentos históricos.

1. Identificar revisión, roles, dependencias, conteos y referencias.
   Capturar respaldos consistentes de PostgreSQL y MongoDB, además de
   cualquier medio local histórico. Por ejemplo, con credenciales privadas,
   guardar `pg_dump -Fc` y `mongodump --archive --gzip` fuera de Git.
   Restaurar ambas copias por separado y validar sus referencias. Preservar
   las copias antes de habilitar el despliegue.
2. Repetir los predicados de preflight del [informe 1D](CARD_CREATION_SERVICE_1D.md).
   Ensayar 008 → 1B.2B → 1G, revisar CHECK, índice de identidad y filas
   conservadas. Los guards vigentes impiden aplicar esta receta al
   original. Su habilitación y los privilegios requieren autorización
   separada.
3. Configurar una cuenta técnica de aplicación sin permisos administrativos,
   otra para migraciones y un rol Mongo limitado por colección. Otorgar
   únicamente permisos aprobados en catálogo, identidad, revisión y Outbox.
   Separar el acceso a GridFS del acceso a la proyección. Inventariar
   proyecciones históricas sin versión o con código en conflicto antes
   de habilitar el consumidor.
4. Tras el cambio autorizado, verificar versión, conteos, índices,
   sesión, replay, archivos y proyección. Si falla, detener escrituras
   y el consumidor. Antes del primer LOCAL puede evaluarse el downgrade
   1G. Después, conciliar esa identidad y las operaciones nuevas o
   restaurar un par SQL/Mongo consistente desde respaldos probados.
   Una restauración implica decidir explícitamente qué escrituras posteriores
   conservar.

## Ensayo manual desde cero

Ejecutar en Bash desde raíz. Los nombres aleatorios y los puertos
publicados en loopback identifican recursos descartables. Los comandos
de operador administrativo solo se usan para inicializar estos motores.

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[dev]'
umask 077
RUN=$(mktemp -d)
S=$(backend/.venv/bin/python -c 'import secrets; print(secrets.token_hex(4))')
PG="pokearena-1g-pg-$S"
MG="pokearena-1g-mongo-$S"
export PG_DB="pokearena_alembic_1g_$S"
export MONGO_DB="pokearena_gridfs_test_$S"
backend/.venv/bin/python - <<'PY' > "$RUN/credenciales"
from secrets import token_hex
for name in ("POSTGRES_PASSWORD", "PA_MIG", "PA_APP",
             "MONGO_INITDB_ROOT_PASSWORD", "PA_MEDIA", "PA_PROJECTION"):
    print(f"{name}={token_hex(24)}")
PY
set -a
. "$RUN/credenciales"
set +a
grep -E '^(POSTGRES_PASSWORD|PA_MIG|PA_APP)=' "$RUN/credenciales" > "$RUN/postgres.env"
grep -E '^(MONGO_INITDB_ROOT_PASSWORD|PA_MEDIA|PA_PROJECTION)=' "$RUN/credenciales" > "$RUN/mongo.env"
docker run --rm -d --name "$PG" --label pokearena.audit=1g-manual \
  -p 127.0.0.1::5432 --tmpfs /var/lib/postgresql/data \
  --env-file "$RUN/postgres.env" -e POSTGRES_USER=validation_admin postgres:16-alpine
docker run --rm -d --name "$MG" --label pokearena.audit=1g-manual \
  -p 127.0.0.1::27017 --tmpfs /data/db --tmpfs /data/configdb \
  --env-file "$RUN/mongo.env" -e MONGO_DB \
  -e MONGO_INITDB_ROOT_USERNAME=validation_admin mongo:7.0
```

Esperar a que PostgreSQL esté listo y preparar los roles. Usar
`pg_isready` y un ping autenticado a MongoDB para verificar los arranques.

```bash
docker exec "$PG" pg_isready -U validation_admin
docker exec -i "$PG" psql -X -v ON_ERROR_STOP=1 -v db="$PG_DB" \
  -U validation_admin -d postgres <<'SQL'
\getenv mig PA_MIG
\getenv app PA_APP
CREATE ROLE pokearena_migrator LOGIN PASSWORD :'mig';
CREATE ROLE orm_media_test LOGIN PASSWORD :'app';
CREATE DATABASE :"db" OWNER pokearena_migrator;
SQL
PG_PORT=$(docker port "$PG" 5432/tcp | sed 's/^127.0.0.1://')
MG_PORT=$(docker port "$MG" 27017/tcp | sed 's/^127.0.0.1://')
export MIGRATION_DATABASE_URL="postgresql+asyncpg://pokearena_migrator:$PA_MIG@127.0.0.1:$PG_PORT/$PG_DB"
export DATABASE_URL="postgresql+asyncpg://orm_media_test:$PA_APP@127.0.0.1:$PG_PORT/$PG_DB"
export MONGO_URL="mongodb://media_test:$PA_MEDIA@127.0.0.1:$MG_PORT/$MONGO_DB"
export PROJECTION_URL="mongodb://projection_test:$PA_PROJECTION@127.0.0.1:$MG_PORT/$MONGO_DB"
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade 1g_local_master_admin
docker exec -i "$PG" psql -X -v ON_ERROR_STOP=1 -U validation_admin -d "$PG_DB" <<'SQL'
GRANT USAGE ON SCHEMA public TO orm_media_test;
GRANT SELECT ON alembic_version, catalog_abilities TO orm_media_test;
GRANT SELECT, UPDATE ON catalog_card_code_counters TO orm_media_test;
GRANT SELECT, INSERT, UPDATE ON catalog_cards, catalog_card_images,
  shared_idempotency_records, shared_outbox, identity_users, identity_sessions TO orm_media_test;
SQL
docker exec -i "$MG" sh -ec 'exec mongosh --quiet --host 127.0.0.1 --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin' <<'JS'
const media = db.getSiblingDB(process.env.MONGO_DB);
const roles = [
  ["media_test", process.env.PA_MEDIA, ["card_assets.files", "card_assets.chunks"],
   ["find", "insert", "remove", "listIndexes", "createIndex"]],
  ["projection_test", process.env.PA_PROJECTION, ["cards_projection"],
   ["find", "insert", "update", "listIndexes"]]
];
media.cards_projection.createIndex({code: 1}, {unique: true});
media.cards_projection.createIndex({name: "text"});
media.cards_projection.createIndex({card_type: 1});
media.cards_projection.createIndex({cost: 1});
for (const [user, pwd, collections, actions] of roles) {
  const role = user + "_rw";
  media.createRole({role, privileges: collections.map(collection => ({
    resource: {db: media.getName(), collection}, actions
  })), roles: []});
  media.createUser({user, pwd, roles: [role]});
}
JS
export ENVIRONMENT=development IDENTITY_LOCAL_ENABLED=true GOOGLE_OAUTH_CLIENT_ID=
export ALLOWED_ORIGINS=http://localhost:5173 MONGO_GRIDFS_BUCKET=card_assets DEBUG=false
(cd backend && .venv/bin/python -m src.modules.identidad.identidad_module --usuario maestro-local)
(cd backend && exec .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 18000 --no-proxy-headers --no-access-log) &
API_PID=$!
```

Con la API lista, usar una imagen válida propia o generar la muestra.
Las credenciales y el Bearer pasan por stdin y archivos privados, sin
incluirse en argumentos de curl. Conservar la misma clave para el replay.

```bash
API=http://127.0.0.1:18000/api/v1
curl --fail-with-body "$API/health"
backend/.venv/bin/python -c 'import getpass,json; print(json.dumps({"username":"maestro-local","password":getpass.getpass("Contraseña local: ")}))' |
  curl -sS --fail-with-body -H 'Content-Type: application/json' --data-binary @- "$API/identity/local/session" > "$RUN/session.json"
backend/.venv/bin/python -c 'import json,sys; print("Authorization: Bearer "+json.load(sys.stdin)["access_token"])' < "$RUN/session.json" > "$RUN/bearer"
curl --fail-with-body -H @"$RUN/bearer" "$API/content/abilities"
backend/.venv/bin/python -c 'from PIL import Image; import sys; Image.new("RGB",(600,840),"orange").save(sys.argv[1])' "$RUN/original.png"
CLAVE=$(backend/.venv/bin/python -c 'from uuid import uuid4; print(uuid4())')
crear() {
  curl -sS --fail-with-body -H @"$RUN/bearer" -H "Idempotency-Key: $CLAVE" \
    -F name=Guardiana -F cost=2 -F power=-5 -F card_type=LUC -F rarity=RARA \
    -F ability_code=HAB-000 -F "image=@$RUN/original.png" "$API/content/cards"
}
crear > "$RUN/carta.json"
crear > "$RUN/replay.json"
cmp "$RUN/carta.json" "$RUN/replay.json"
cat "$RUN/carta.json"
CARTA_ID=$(backend/.venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["id"])' < "$RUN/carta.json")
docker exec -i "$PG" psql -X -v id="$CARTA_ID" -U validation_admin -d "$PG_DB" <<'SQL'
SELECT c.id, c.code, c.version, i.state, i.original_storage_key,
       i.thumbnail_storage_key, i.thumbnail_width, i.thumbnail_height, o.status
FROM catalog_cards c JOIN catalog_card_images i ON i.id=c.image_id
JOIN shared_outbox o ON o.aggregate_id=c.id WHERE c.id=:'id';
SQL
(cd backend && MONGO_URL="$PROJECTION_URL" .venv/bin/python -m src.database.outbox_worker --once)
export CARTA_ID
backend/.venv/bin/python - <<'PYVERIFY'
import asyncio, os
from bson import ObjectId
from gridfs import AsyncGridFSBucket
from pymongo import AsyncMongoClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    base, ident = os.environ["MONGO_DB"], os.environ["CARTA_ID"]
    engine = create_async_engine(os.environ["DATABASE_URL"], hide_parameters=True)
    try:
        async with engine.connect() as conn:
            original, mini, codigo, estado = (await conn.execute(text("""
                SELECT i.original_storage_key, i.thumbnail_storage_key, c.code, o.status
                FROM catalog_cards c JOIN catalog_card_images i ON i.id=c.image_id
                JOIN shared_outbox o ON o.aggregate_id=c.id WHERE c.id=:id
            """), {"id": ident})).one()
        assert estado == "PROCESSED"
        async with AsyncMongoClient(os.environ["MONGO_URL"]) as medios:
            bucket = AsyncGridFSBucket(medios[base], bucket_name="card_assets")
            for ref in (original, mini):
                async with await bucket.open_download_stream(
                    ObjectId(ref.removeprefix("gridfs:"))
                ) as archivo:
                    assert len(await archivo.read()) == archivo.length
        async with AsyncMongoClient(os.environ["PROJECTION_URL"]) as mongo:
            doc = await mongo[base].cards_projection.find_one({"_id": ident})
            assert doc and doc["code"] == codigo and doc["image_status"] == "READY"
            print("Proyección confirmada", codigo, doc["aggregate_version"])
    finally:
        await engine.dispose()

asyncio.run(main())
PYVERIFY
curl -sS --fail-with-body -X DELETE -H @"$RUN/bearer" "$API/identity/session"
kill "$API_PID"
wait "$API_PID"
docker inspect --format '{{index .Config.Labels "pokearena.audit"}}' "$PG" "$MG"
# Solo si ambas etiquetas son 1g-manual y los nombres coinciden con los de este ensayo:
docker stop "$PG" "$MG"
rm -f "$RUN/credenciales" "$RUN/postgres.env" "$RUN/mongo.env" "$RUN/session.json" "$RUN/bearer" \
  "$RUN/original.png" "$RUN/carta.json" "$RUN/replay.json"
rmdir "$RUN"
unset DATABASE_URL MIGRATION_DATABASE_URL MONGO_URL PROJECTION_URL IDENTITY_LOCAL_ENABLED
unset PA_MIG PA_APP PA_MEDIA PA_PROJECTION POSTGRES_PASSWORD MONGO_INITDB_ROOT_PASSWORD
```

Para repetir la suite integral se requieren copias nuevas y un
administrador aún sin aprovisionar. El ensayo manual usa sus propios
recursos y permite verificar el flujo sin preparar el resto de destinos
de regresión.
