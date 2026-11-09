# IA-5C — Runbook de corte de Poké-Arena

**Estado:** procedimiento preparado. El corte, el inicio de servicios sobre originales y la recuperación requieren autorización independiente. Ejecutar desde la raíz del repositorio, con Bash, Docker local, PostgreSQL 16 y MongoDB 7. Identificar el commit candidato y el procedimiento de reversión antes de reservar la ventana.

## 1. Destinos, responsables y condiciones de aborto

| Proceso | Destino PostgreSQL | Destino MongoDB | Habilitación |
|---|---|---|---|
| Alembic | `127.0.0.1:5432/pokearena_db`, `pokearena_original_migrator` | Sin cliente MongoDB | `ORIGINAL_MIGRATION_ENABLED=true` |
| FastAPI | Mismo destino, `poke_api_user` | `127.0.0.1:27017/pokearena_catalog`, `poke_api_mongo` | `ORIGINAL_RUNTIME=api` |
| Outbox | Mismo destino, `poke_api_user` | Mismo destino MongoDB, `poke_outbox_mongo` | `ORIGINAL_RUNTIME=outbox` |

Para los tres procesos usar `ENVIRONMENT=development`, IP y puertos explícitos. Las URI MongoDB requieren `authSource=pokearena_catalog&directConnection=true`. Mantener `IDENTITY_LOCAL_ENABLED=false` en originales. Las habilitaciones se pasan a cada comando. Mantenerlas fuera de los archivos de entorno compartidos. Usar el gestor privado del operador para inyectar URLs codificadas y credenciales. Mantener `set +x` y evitar volcados de entorno.

Abortar ante un destino, dueño, esquema, revisión o rol ambiguo, un escritor activo, fallo en respaldo o restauración de ensayo, ACL inesperadas, revisión distinta de `008_flex_card_img_dims`, divergencia histórica o fallo de salud, OIDC, GridFS u Outbox. Detener nuevos ingresos y escrituras hasta identificar el último estado confirmado. Si falla Alembic, comprobar la revisión persistida antes de decidir entre corregir el prerrequisito y restaurar. PostgreSQL aplica la cadena con DDL transaccional.

## 2. Preflight y respaldo bajo ventana de mantenimiento

1. Suspender el acceso de clientes y detener FastAPI, Outbox, tareas de carga y otros escritores con su supervisor. Mantener el bloqueo de accesos públicos hasta terminar la aceptación. Verificar procesos del host y de Docker, sesiones y contadores DML de PostgreSQL, y operaciones activas y contadores por colección de MongoDB. Repetir las observaciones antes, durante y después de las capturas. Los contadores globales MongoDB incluyen actividad ajena al catálogo.
2. Confirmar los IDs, montajes, versiones y mapeos de los dos contenedores existentes. Tomar una línea base de tablas, carta, imagen, proyección, habilidad, identidades, sesiones, idempotencia y eventos. Guardar los roles, membresías, propietarios, ACL y definiciones de roles MongoDB en el directorio privado de la ventana. Los archivos de datos por base no sustituyen el inventario de autorización.
3. Generar un par nuevo y ensayar su restauración en destinos desechables. Comparar los datos con el inventario y conservar las huellas. El par de IA-5B.1 es la evidencia del ensayo anterior.

```bash
git --no-optional-locks status --short --branch
git rev-parse HEAD
docker inspect --format '{{.Name}} {{.State.Status}} {{json .NetworkSettings.Ports}} {{json .Mounts}}' pokearena-postgres pokearena-mongo
docker ps --format '{{.Names}} {{.Ports}}'

umask 077
RUN=$(mktemp -d "$HOME/pokearena-backups/ia5b/corte-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
docker exec pokearena-postgres sh -ec '
  export PGPASSWORD="$POSTGRES_PASSWORD" PGOPTIONS="-c default_transaction_read_only=on"
  exec psql -X -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d pokearena_db -v ON_ERROR_STOP=1
' <<'SQL'
SELECT current_database(), current_user, inet_server_port(), version();
SELECT version_num FROM alembic_version;
SELECT application_name, state, count(*) FROM pg_stat_activity
WHERE datname=current_database() AND pid<>pg_backend_pid() GROUP BY 1,2;
SELECT tup_inserted,tup_updated,tup_deleted FROM pg_stat_database WHERE datname=current_database();
SELECT relname,relowner::regrole,relacl FROM pg_class
WHERE relnamespace='public'::regnamespace AND relkind IN ('r','S') ORDER BY relname;
SQL

docker exec pokearena-postgres sh -ec '
  export PGPASSWORD="$POSTGRES_PASSWORD" PGOPTIONS="-c default_transaction_read_only=on"
  exec pg_dumpall -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" \
    --no-password --roles-only --no-role-passwords
' > "$RUN/postgres-roles.sql"
docker exec pokearena-mongo mongosh --nodb --quiet --eval '
  const auth = encodeURIComponent(process.env.MONGO_INITDB_ROOT_USERNAME) + ":" +
    encodeURIComponent(process.env.MONGO_INITDB_ROOT_PASSWORD);
  const server = new Mongo("mongodb://" + auth + "@127.0.0.1:27017/admin?directConnection=true");
  const admin = server.getDB("admin"), catalog = server.getDB("pokearena_catalog");
  const active = admin.aggregate([{$currentOp:{allUsers:true,idleConnections:true,localOps:true}}])
    .toArray().filter(x => x.client)
    .map(x => ({app:x.appName, active:x.active, ns:x.ns, op:x.op}));
  const top = admin.runCommand({top:1});
  printjson({version:admin.runCommand({buildInfo:1}).version, active,
    totals:Object.fromEntries(Object.entries(top.totals).filter(([k]) => k.startsWith("pokearena_catalog."))),
    users:catalog.runCommand({usersInfo:1,showCredentials:false}),
    roles:catalog.runCommand({rolesInfo:1,showPrivileges:true})});
' > "$RUN/mongo-preflight.json"

docker exec pokearena-postgres sh -ec '
  export PGPASSWORD="$POSTGRES_PASSWORD" PGOPTIONS="-c default_transaction_read_only=on"
  exec pg_dump -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d pokearena_db \
    --no-password -Fc --serializable-deferrable --lock-wait-timeout=3s
' > "$RUN/postgres.dump"
docker exec -i pokearena-mongo bash -ec '
  exec mongorestore --version
' > "$RUN/mongo-tools.txt"
docker exec -i pokearena-mongo bash -ec '
  exec mongodump --config=/dev/fd/3 --host 127.0.0.1 --port 27017 \
    --username "$MONGO_INITDB_ROOT_USERNAME" --authenticationDatabase admin \
    --db pokearena_catalog --archive --gzip \
    3< <(mongosh --nodb --quiet --eval "print(JSON.stringify({password:process.env.MONGO_INITDB_ROOT_PASSWORD}))")
' > "$RUN/mongo.archive.gz"
docker exec -i pokearena-postgres pg_restore --list < "$RUN/postgres.dump" > "$RUN/postgres.toc"
docker exec -i pokearena-postgres pg_restore --file=- < "$RUN/postgres.dump" > /dev/null
gzip -t "$RUN/mongo.archive.gz"
(cd "$RUN" && shasum -a 256 postgres.dump mongo.archive.gz postgres.toc > SHA256SUMS &&
  shasum -a 256 -c SHA256SUMS)
```

Comprobar códigos de salida de todos los comandos. En MongoDB usar `hello`, `buildInfo`, `currentOp` y `top` con el cliente administrativo. Registrar UTC, revisión, conteos y huellas lógicas. Además de `gzip -t`, restaurar en desechables para verificar BSON, documentos, índices y coincidencia PostgreSQL/MongoDB. La carta histórica `PKA-PLA-001` y su evento `PROCESSED` son parte de la línea base. Antes de migrar, validar dimensiones, proporción 5:7 y miniatura WebP completa para cualquier imagen histórica `READY`, según la primera revisión de la cadena.

## 3. Migración y ACL PostgreSQL

Usar `psql -X -h 127.0.0.1 -p 5432 -d pokearena_db -U postgres -v ON_ERROR_STOP=1` con contraseña administrada en `PGPASSWORD`. Los ejemplos asumen que `postgres` es el dueño histórico verificado. Si el inventario discrepa, detenerse y ajustar el plan de devolución de propiedad. Confirmar que `poke_api_user` existe antes del upgrade, es un rol técnico sin membresías elevadas ni privilegios globales. Inyectar `CUT_MIGRATION_PASSWORD` desde el gestor privado.

```sql
\getenv migrator_password CUT_MIGRATION_PASSWORD
BEGIN;
CREATE ROLE pokearena_original_migrator LOGIN PASSWORD :'migrator_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT CONNECT ON DATABASE pokearena_db TO pokearena_original_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO pokearena_original_migrator;
GRANT REFERENCES (id) ON public.catalog_cards TO pokearena_original_migrator;
ALTER TABLE public.alembic_version OWNER TO pokearena_original_migrator;
ALTER TABLE public.catalog_card_images OWNER TO pokearena_original_migrator;
ALTER TABLE public.identity_users OWNER TO pokearena_original_migrator;
COMMIT;
```

`CUT_MIGRATION_URL` debe apuntar exclusivamente a `pokearena_original_migrator@127.0.0.1:5432/pokearena_db` con el driver `postgresql+asyncpg`, contraseña y sin parámetros de redirección. Confirmar en solo lectura `008_flex_card_img_dims` y la existencia de `poke_api_user` antes de ejecutar. El único punto de entrada autorizado es `migrate_original.py`, que acepta cero argumentos de operación, fija `upgrade 014_identity_account_immutable` y habilita internamente una sola configuración de Alembic. El opt-in de entorno es un requisito adicional.

```bash
(cd backend && ENVIRONMENT=development ORIGINAL_RUNTIME=disabled ORIGINAL_MIGRATION_ENABLED=true \
  MIGRATION_DATABASE_URL="$CUT_MIGRATION_URL" .venv/bin/python -B migrate_original.py)
```

Para originales están prohibidos la CLI directa de Alembic, `stamp` (incluido `--purge`), `downgrade`, `revision`, `revision --autogenerate`, conexiones inyectadas y cualquier otro destino de upgrade. Si el punto de entrada devuelve un código distinto de cero, detener el corte y consultar la revisión, el trigger y las ACL en solo lectura. Si la revisión sigue en `008`, conciliar la causa y devolver la propiedad y los permisos temporales antes de cerrar la ventana. Si el estado difiere del esperado, seguir el rollback del par de bases de la sección 6. Mantener los escritores detenidos durante el diagnóstico.

Revisar la traza en orden `1b2b_card_image_integrity`, `1g_local_master_admin`, `011_locations_full`, `012_player_profiles_inventory`, `013_initial_pack_opened_at`, `014_identity_account_immutable`. Antes de aplicar otras ACL, ejecutar la comprobación de permisos de `014`.

```sql
SELECT version_num FROM alembic_version;
SELECT tgname,tgenabled,pg_get_triggerdef(oid) FROM pg_trigger
WHERE tgrelid='public.identity_users'::regclass AND NOT tgisinternal;
SELECT conrelid::regclass,conname,convalidated,pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid IN ('catalog_card_images'::regclass,'identity_users'::regclass,
                   'player_profiles'::regclass,'player_cards'::regclass,'cube_transactions'::regclass);
SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2;
SELECT a.attname,has_column_privilege('poke_api_user','identity_users',a.attname,'UPDATE')
FROM pg_attribute a WHERE a.attrelid='identity_users'::regclass AND a.attnum>0 AND NOT a.attisdropped;
SELECT p,has_table_privilege('poke_api_user','identity_users',p)
FROM unnest(ARRAY['UPDATE','DELETE','TRUNCATE']) AS p;
```

Exigir `UPDATE` solamente en `email`, `updated_at`, `local_failed_attempts` y `local_blocked_until` en Identidad, y los tres permisos de tabla anteriores en falso. A continuación devolver la propiedad y completar ACL del rol técnico. No extender permisos a las tablas de ubicaciones por este corte.

```sql
BEGIN;
ALTER TABLE public.alembic_version OWNER TO postgres;
ALTER TABLE public.catalog_card_images OWNER TO postgres;
ALTER TABLE public.identity_users OWNER TO postgres;
ALTER TABLE public.locations OWNER TO postgres;
ALTER TABLE public.outbox_events OWNER TO postgres;
ALTER TABLE public.idempotency_records OWNER TO postgres;
ALTER TABLE public.player_profiles OWNER TO postgres;
ALTER TABLE public.player_cards OWNER TO postgres;
ALTER TABLE public.cube_transactions OWNER TO postgres;
ALTER FUNCTION public.reject_identity_account_change() OWNER TO postgres;
REVOKE REFERENCES (id) ON public.catalog_cards FROM pokearena_original_migrator;
REVOKE USAGE, CREATE ON SCHEMA public FROM pokearena_original_migrator;
REVOKE CONNECT ON DATABASE pokearena_db FROM pokearena_original_migrator;
ALTER ROLE pokearena_original_migrator NOLOGIN;

GRANT CONNECT ON DATABASE pokearena_db TO poke_api_user;
GRANT USAGE ON SCHEMA public TO poke_api_user;
GRANT SELECT ON public.alembic_version,public.catalog_abilities TO poke_api_user;
GRANT SELECT,UPDATE ON public.catalog_card_code_counters TO poke_api_user;
GRANT SELECT,INSERT,UPDATE ON public.catalog_cards,public.catalog_card_images,
    public.shared_idempotency_records,public.shared_outbox,public.identity_sessions TO poke_api_user;
GRANT SELECT,INSERT ON public.identity_users,public.player_profiles,
    public.player_cards,public.cube_transactions TO poke_api_user;
GRANT UPDATE (cubes,has_received_initial_collection,updated_at,initial_pack_opened_at)
    ON public.player_profiles TO poke_api_user;
COMMIT;

SELECT p,has_table_privilege('poke_api_user','cube_transactions',p)
FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE']) AS p;
SELECT has_column_privilege('poke_api_user','player_profiles','initial_pack_opened_at','UPDATE');
```

Confirmar conectividad con el rol técnico y `SHOW transaction_read_only` durante los probes de lectura. Validar ACL efectivas, incluidas membresías, `PUBLIC` y `has_schema_privilege(...,'CREATE')`. Comparar nuevamente la identidad, las sesiones, la carta, la habilidad, la idempotencia y el Outbox históricos con el respaldo.

## 4. ACL MongoDB y comprobación administrativa

Usar un shell administrativo conectado al destino original ya verificado. Preservar en el inventario de rollback los roles anteriores de `poke_api_mongo`. Verificar ausencia de los dos roles nuevos y de `poke_outbox_mongo`; si existen, comparar sus capacidades y abortar ante diferencias. Inyectar `CUT_MONGO_WORKER_PASSWORD` desde el gestor privado. El usuario API conserva su contraseña.

```javascript
const target = db.getSiblingDB("pokearena_catalog");
if (target.getName() !== "pokearena_catalog" ||
    !process.env.CUT_MONGO_WORKER_PASSWORD ||
    !target.cards_projection.getIndexes().some(i => i.unique && i.key.code === 1)) quit(2);
if (!target.getUser("poke_api_mongo") || target.getUser("poke_outbox_mongo") ||
    target.getRole("pokearena_original_api") || target.getRole("pokearena_original_outbox")) quit(2);
const grant = (collection, actions) => ({
  resource: {db: target.getName(), collection}, actions
});
const media = ["card_assets.files", "card_assets.chunks"].map(c =>
  grant(c, ["find", "insert", "remove", "listIndexes", "createIndex"]));
target.createRole({
  role: "pokearena_original_api", roles: [],
  privileges: [...media, grant("cards_projection", ["find"])]
});
target.createRole({
  role: "pokearena_original_outbox", roles: [],
  privileges: [grant("cards_projection", ["find", "insert", "update", "listIndexes"])]
});
target.updateUser("poke_api_mongo", {roles: ["pokearena_original_api"]});
target.createUser({
  user: "poke_outbox_mongo", pwd: process.env.CUT_MONGO_WORKER_PASSWORD,
  roles: ["pokearena_original_outbox"]
});
```

Verificar `connectionStatus` con cada usuario, lectura de catálogo con API y `listIndexes` con Outbox. Comprobar ACL desde administración y contrastar con las pruebas positivas y negativas del clon. Conservar las referencias históricas de MongoDB.

Antes del primer ingreso, confirmar privadamente el `sub` con un token de Google verificado para el Client ID efectivo, con emisor, audiencia, firma y expiración válidos. La comprobación previa se hace fuera del endpoint de login de Poké-Arena. Comparar ese valor con la allowlist efectiva sin imprimirlo. Si se autoriza por correo, comprobar `email_verified=true` y la coincidencia del correo normalizado. Abortar ante una identidad existente `PLAYER` o una discrepancia. El tipo de cuenta permanece inmutable.

```sql
\getenv subject GOOGLE_ADMIN_SUB_CONFIRMADO
SELECT role FROM public.identity_users
WHERE provider='GOOGLE' AND provider_subject=:'subject';
```

La consulta debe devolver `PLATFORM_ADMIN` o cero filas. En el segundo caso, exigir coincidencia con la allowlist antes de autorizar el primer ingreso. Comparar los valores efectivos de `GOOGLE_OAUTH_CLIENT_ID` (FastAPI) y `VITE_GOOGLE_OAUTH_CLIENT_ID` (React) en el canal privado, registrando solo si están presentes y coinciden. Mantener bloqueado el ingreso público hasta verificar la cuenta administrativa prevista.

## 5. Arranque y aceptación controlados

Inyectar `CUT_APP_PG_URL`, `CUT_API_MONGO_URL`, `CUT_WORKER_MONGO_URL`, el Client ID y la allowlist en sesiones privadas. Levantar los procesos por separado. Mantener el supervisor y registrar sus PID. Para la primera carta, usar el portal administrativo con una clave de idempotencia nueva y guardar esa clave y la imagen en el expediente privado del corte.

```bash
(cd backend && ENVIRONMENT=development ORIGINAL_MIGRATION_ENABLED=false ORIGINAL_RUNTIME=api \
  DATABASE_URL="$CUT_APP_PG_URL" MONGO_URL="$CUT_API_MONGO_URL" MONGO_DB=pokearena_catalog \
  MONGO_GRIDFS_BUCKET=card_assets IDENTITY_LOCAL_ENABLED=false DEBUG=false \
  .venv/bin/python -B -m uvicorn src.main:app --host 127.0.0.1 --port 8000)

curl -fsS http://127.0.0.1:8000/api/v1/health

(cd backend && ENVIRONMENT=development ORIGINAL_MIGRATION_ENABLED=false ORIGINAL_RUNTIME=outbox \
  DATABASE_URL="$CUT_APP_PG_URL" MONGO_URL="$CUT_WORKER_MONGO_URL" MONGO_DB=pokearena_catalog \
  OUTBOX_BATCH_SIZE=1 OUTBOX_CONCURRENCY=1 DEBUG=false \
  .venv/bin/python -B -m src.database.outbox_worker --once)
```

1. Confirmar `healthy` y los dos motores conectados. Validar la sesión del administrador con `GET /api/v1/identity/me` y el rechazo de su consulta de paquete. Consultar `GET /api/v1/content/cards/PKA-PLA-001` y comprobar `ability_code=HAB-000`.
2. Verificar la cola antes del primer `--once`. Confirmar que la carta controlada quedó `READY`, que sus dos archivos son recuperables y que el evento pasó a `PROCESSED`. Cotejar ID, código, versión, habilidad y rareza entre SQL y MongoDB. Comprobar búsqueda por código y nombre. Si el ciclo pasa, iniciar el worker en modo continuo con el mismo entorno y sin `--once`.
3. Crear por el portal hasta alcanzar 20 comunes distintas con imágenes `READY` y proyecciones conciliadas. El mínimo es 15. Con menos de 15, comprobar `PENDING_CATALOG`, cero inventario, cubos y movimientos. Con catálogo suficiente, el jugador previamente pendiente debe seguir pendiente al consultar y recibir 15 cartas distintas y 1.000 cubos en el siguiente login, con un único movimiento `INITIAL_COLLECTION`. Confirmar que reingreso y reapertura conservan saldo, inventario y `opened_at`.

## 6. Rollback coordinado PostgreSQL y MongoDB

Detener ambos servicios y bloquear escritores. Si ya hubo escrituras posteriores a la captura, respaldar primero ese estado para conciliación y conservar los volúmenes actuales. La restauración del par anterior excluye los cambios aceptados después de su captura. El responsable debe aprobar ese punto de recuperación. Restaurar y validar el par en volúmenes de rescate nuevos antes de cambiar la publicación de puertos.

Los siguientes comandos suponen volúmenes de rescate recién creados, puertos de ensayo libres, credenciales privadas en las variables de los contenedores y `rollback-pg-roles.sql` revisado. Este archivo debe recrear los roles referenciados por el TOC con las credenciales recuperadas del gestor privado. Usar el inventario MongoDB anterior para recrear la cuenta y el rol de la aplicación que se va a restaurar.

```bash
docker volume create pokearena_pg_rollback
docker volume create pokearena_mongo_rollback
docker volume create pokearena_mongo_config_rollback
docker run -d --pull=never --name pokearena-pg-rollback -p 127.0.0.1:25485:5432 \
  -e POSTGRES_USER=postgres -e POSTGRES_DB=pokearena_db -e POSTGRES_PASSWORD \
  -v pokearena_pg_rollback:/var/lib/postgresql/data postgres:16-alpine
docker run -d --pull=never --name pokearena-mongo-rollback -p 127.0.0.1:37085:27017 \
  -e MONGO_INITDB_ROOT_USERNAME -e MONGO_INITDB_ROOT_PASSWORD \
  -v pokearena_mongo_rollback:/data/db -v pokearena_mongo_config_rollback:/data/configdb mongo:7.0 --auth
docker exec -i pokearena-pg-rollback psql -X -U postgres -d postgres -v ON_ERROR_STOP=1 \
  < "$RUN/rollback-pg-roles.sql"
docker exec -i pokearena-pg-rollback pg_restore -U postgres -d pokearena_db \
  --exit-on-error --single-transaction < "$RUN/postgres.dump"
docker exec -i pokearena-mongo-rollback bash -ec '
  exec mongorestore --config=/dev/fd/3 --host 127.0.0.1 --port 27017 \
    --username "$MONGO_INITDB_ROOT_USERNAME" --authenticationDatabase admin \
    --archive --gzip --nsInclude "pokearena_catalog.*" --stopOnError \
    3< <(mongosh --nodb --quiet --eval "print(JSON.stringify({password:process.env.MONGO_INITDB_ROOT_PASSWORD}))")
' < "$RUN/mongo.archive.gz"
```

Verificar primero en `25485/37085` la revisión 008, los índices, las huellas lógicas, la carta, el evento, las identidades y la proyección. Comprobar las ACL y la autenticación de la versión anterior del backend. Confirmar que el archivo de composición del rescate apunta a **ambos** volúmenes restaurados antes de levantar servicios. Mantener el tráfico cerrado durante el intercambio.

```bash
docker stop pokearena-pg-rollback pokearena-mongo-rollback
docker stop pokearena-postgres pokearena-mongo
docker rename pokearena-postgres pokearena-postgres-postcorte
docker rename pokearena-mongo pokearena-mongo-postcorte
docker compose --project-name pokearena-rollback -f docker-compose.yml up -d --no-deps postgres mongo
```

Para el último comando, suministrar desde el entorno privado `POSTGRES_VOLUME_NAME=pokearena_pg_rollback`, `MONGO_VOLUME_NAME=pokearena_mongo_rollback`, `MONGO_CONFIG_VOLUME_NAME=pokearena_mongo_config_rollback`, puertos originales, credenciales del rescate y la red externa aprobada. Verificar los nuevos IDs, montajes y mapeos. Reiniciar únicamente una versión de aplicación compatible con `008`, con sus permisos y credenciales restaurados. Abrir tráfico tras verificar ambas bases juntas. Los volúmenes posteriores al corte quedan preservados para diagnóstico o conciliación.
