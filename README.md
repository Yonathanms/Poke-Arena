# Poké-Arena – Plataforma de Cartas Coleccionables

Repositorio del proyecto para el curso **CE-116: Diseño y Calidad en Productos Tecnológicos** (ITCR).  
Equipo de Desarrollo: **MAFY**

---

## Requisitos Previos

Antes de comenzar, asegúrate de tener instalado en tu máquina:
1. **Git:** ([Descargar Git](https://git-scm.com/))
2. **Docker Desktop:** Debe estar iniciado y corriendo ([Descargar Docker Desktop](https://www.docker.com/products/docker-desktop/))
3. **Python >=3.12 y <3.14** (según `backend/pyproject.toml`): Con `pip` habilitado en las variables de entorno ([Descargar Python](https://www.python.org/downloads/))
4. **Node.js (v18 o v20 LTS):** Con `npm` ([Descargar Node.js](https://nodejs.org/))

---

## Instalación y Puesta en Marcha (Paso a Paso)

Todos los comandos iniciales se ejecutan desde la **raíz del proyecto** (`Poke-Arena/`).

### Paso 1: Configurar el entorno e instalar dependencias
Abre una terminal en la raíz del proyecto y ejecuta:

```powershell
# Ubicación: Poke-Arena/
python manage.py install
```

Este comando automatiza todo:
* Usa el `.env` privado que ya exista. La plantilla `.env.example` dejó de versionarse en esta rama, por lo que un checkout nuevo necesita que el operador prepare la configuración privada antes de ejecutar el instalador.
* Crea el entorno virtual de Python (`backend/.venv`) e instala los paquetes necesarios.
* Descarga e instala los paquetes de Node.js en `frontend/`.

Mantén `.env` fuera de Git. Para el catálogo aislado, proporciona los destinos y las credenciales técnicas por un canal privado.

---

### Paso 2: Iniciar las Bases de Datos en Docker
La Entrega 1A se completó sobre los volúmenes existentes y las cuentas técnicas quedaron verificadas. Revisa el inventario y los respaldos al final de este documento antes de cualquier operación. El atajo desde raíz inicia PostgreSQL 16 y MongoDB 7 sin recrear contenedores existentes:

```powershell
# Ubicación: Poke-Arena/
python manage.py dbs
```
*(Equivale a `docker compose up -d --no-recreate`; no aplica cambios de configuración a contenedores existentes).*

> **Nota importante:** Docker se utiliza exclusivamente para levantar los servidores de bases de datos. El código del backend y del frontend se corre directamente en local.

---

### Paso 3: Aprovisionar Base de Datos y Administrador Local (setup-dev)

> Procedimiento legado con escrituras. En esta rama apunta a los contenedores locales en los puertos originales. Para reproducir CI-5, utiliza destinos desechables explícitos. Para consultar el catálogo CI-4 existente, usa solo el dry-run en el par aislado.
Para configurar automáticamente las tablas en PostgreSQL mediante Alembic, crear los índices de MongoDB y registrar el usuario Administrador Maestro para pruebas locales, ejecuta desde la raíz:

```powershell
# Ubicación: Poke-Arena/
python manage.py setup-dev
```

Este comando realiza las siguientes tareas de forma segura y automatizada:
* Verifica y asegura la red Docker (`poke-arena_default`) y los volúmenes persistentes.
* Crea y configura la base de datos de desarrollo `pokearena_alembic_frontend_dev` con el usuario migrador `pokearena_migrator`.
* Ejecuta `alembic upgrade heads`. La cabeza actual es `014_identity_account_immutable`.
* Otorga privilegios de tabla al usuario de aplicación en PostgreSQL.
* Crea el índice único en MongoDB (`cards_projection.code`).
* Aprovisiona al Administrador Maestro local en `identity_users` con hash scrypt:
  * **Usuario:** `maestro-local`
  * **Contraseña:** la configurada explícitamente por el operador para ese entorno de desarrollo.
  * **Rol asignado:** `PLATFORM_ADMIN`

---

## Flujo de Trabajo Diario (Dividir Terminales en VS Code)

Para desarrollar cómodamente con recarga automática (*hot-reload*), abre **dos terminales** en VS Code:

### Terminal 1: Backend (FastAPI)
Navega a la carpeta del backend, activa el entorno virtual y levanta el servidor de la API:

```powershell
# Ubicación de la terminal: Poke-Arena\backend
cd backend
.venv\Scripts\activate
uvicorn src.main:app --reload --port 8000
```
*(Atajo alternativo desde la raíz: `python manage.py dev-backend`)*

* Documentación Swagger interactiva: http://localhost:8000/docs
* Verificación de salud (Healthcheck): http://localhost:8000/api/v1/health

---

### Terminal 2: Frontend (React + Vite)
Navega a la carpeta del frontend y ejecuta el servidor de desarrollo:

```powershell
# Ubicación de la terminal: Poke-Arena\frontend
cd frontend
npm run dev
```
*(Atajo alternativo desde la raíz: `python manage.py dev-frontend`)*

* Aplicación Web en vivo: http://localhost:5173
  * **Portal de Administración (Crear Carta - 2.1.1):** Ingresa con las credenciales de administrador local:
    * **Usuario:** `maestro-local`
    * **Contraseña:** la configurada explícitamente por el operador para ese entorno de desarrollo.
  * **Portal de Jugador (Buscar Carta - 2.1.2):** En la pantalla de login, haz clic en el enlace superior *"Ver Catálogo Público (Jugador) →"* o ingresa directamente con el parámetro de vista: http://localhost:5173/?view=player

---

## Comandos de Utilidad (`manage.py`)

Todos estos comandos se ejecutan desde la raíz del proyecto (`Poke-Arena/`):

| Comando | Descripción |
| :--- | :--- |
| **`python manage.py install`** | Instala dependencias de backend y frontend. Requiere configuración privada en un checkout nuevo. |
| **`python manage.py env`** | Usa el `.env` existente o copia una plantilla local. Esta rama no versiona la plantilla. |
| **`python manage.py dbs`** | Enciende PostgreSQL y MongoDB en Docker. |
| **`python manage.py setup-dev`** | Aprovisionamiento legado con escrituras en PostgreSQL, MongoDB e Identidad LOCAL. |
| **`python manage.py stop`** | Detiene los contenedores de Docker conservando los datos guardados. |
| **`python manage.py clean`** | Comando destructivo legado: NO utilizar durante esta entrega. |
| **`python manage.py status`** | Consulta el estado y puertos de los contenedores Docker. |
| **`python manage.py lint`** | Verifica estilo y tipado estricto con Ruff y Mypy. |
| **`python manage.py dev-backend`** | Atajo para arrancar FastAPI en `:8000`. |
| **`python manage.py dev-frontend`** | Atajo para arrancar React / Vite en `:5173`. |

---

## Estructura del Repositorio

>

```text
Poke-Arena/
├── docker-compose.yml              # Bases de datos: PostgreSQL (:5432) y MongoDB (:27017)
├── manage.py                       # CLI para automatizar tareas del equipo
│
├── frontend/                       # APLICACIÓN WEB (React + TypeScript + Tailwind)
│   └── src/
│       ├── 📁 web_admin/           # Portal de Administradores (Gestión de Catálogo)
│       ├── 📁 web_player/          # Portal de Jugadores (Catálogo y perfil)
│       └── 📁 portal_b2b/          # Portal de Organizaciones B2B (Torneos)
│
└── backend/                        # API REST (FastAPI + SQLAlchemy + MongoDB)
    ├── alembic/                    # Historial de versiones y migraciones de PostgreSQL
    └── src/
        ├── main.py                 # Punto de entrada de FastAPI y rutas
        ├── database/               # Conexiones físicas a PostgreSQL, MongoDB y outbox_worker
        ├── shared/                 # Capa Transversal (Configuración .env, roles, errores RFC 7807)
        └── modules/                # LÓGICA DE NEGOCIO Y DOMINIO (Capa 3 de la Arquitectura)
            ├── 📁 catalogo/        # Gestión de cartas y ubicaciones
            ├── 📁 identidad/       # Cuentas, sesiones y autenticación
            ├── 📁 jugadores/       # Colecciones, perfiles, mazos e inventario
            ├── 📁 torneos/         # Gestión de torneos B2B y llaves de API
            └── 📁 motor_juego/     # Motor de batalla puro y máquina de estados
```

> **Regla de oro para crear código nuevo:**  
> Cada submódulo (ejemplo: `catalogo/gestion_cartas`) contiene 5 carpetas de arquitectura hexagonal:
> 1. `controllers/`: Endpoints HTTP y validación con Pydantic DTOs.
> 2. `services/`: Reglas del negocio y casos de uso.
> 3. `domain/`: Entidades y reglas puras, sin ORM; mapeos SQL en `adapters/`.
> 4. `ports/`: Interfaces abstractas (contratos).
> 5. `adapters/`: Repositorios concretos de PostgreSQL o MongoDB y adaptadores externos.


## Entrega 1A — Estado y operación segura (2026-11-06)

**Entrega 1A completada con autorización explícita posterior:** usuarios técnicos configurados y contenedores recreados de forma controlada. Se mantuvieron imágenes locales PostgreSQL 16/MongoDB 7, volúmenes, red, puertos y registros. No se ejecutó recuperación Alembic, 1B, implementación GridFS ni workers. FastAPI se inició temporalmente para probar HTTP y se detuvo limpiamente; las bases permanecen saludables.

### Recursos identificados

| Recurso | Estado preservado |
|---|---|
| PostgreSQL | `pokearena-postgres`, PostgreSQL 16, volumen `pokearena_pgmaster_data` en `/var/lib/postgresql/data` |
| MongoDB | `pokearena-mongo`, MongoDB 7, volumen `pokearena_mongo_data` en `/data/db` |
| Mongo config | Volumen externo existente en `/data/configdb`; nombre exacto conservado en `.env` privado y `docker inspect` |
| Red | `poke-arena_default`, compartida únicamente por los dos servicios originales al inspeccionarla |
| Puertos | `127.0.0.1:5432` y `127.0.0.1:27017` |
| Bases SQL | `poke_arena`, `pokearena_db`, `pokearena_test`, `postgres`; todas respaldadas. `pokearena_db` contiene el esquema de 12 tablas/revisión 008 del catálogo auditado |
| Mongo de aplicación | `pokearena_catalog`, proyección `cards_projection` e índices conservados |

Compose ahora declara los volúmenes y la red como **externos**: no los crea vacíos si faltan ni administra su eliminación. Esto conserva los recursos reales; no sustituye un respaldo ni impide eliminaciones manuales ajenas a Compose. Los nombres configurables deben coincidir con `docker inspect`, no elegirse para crear otra instalación.

**Montajes obsoletos retirados con autorización:** las fuentes ya no estaban en el árbol y los binds no eran legibles dentro de los contenedores:

- `backend/src/database/postgresql/init/10_create_application_role.sh`
- `backend/src/database/mongodb/init/10_create_application_user.js`

Se verificaron destinos exclusivos `/docker-entrypoint-initdb.d`, CMD/entrypoints estándar de las imágenes oficiales y bases ya inicializadas. Los entrypoints solo utilizan esos archivos durante inicialización de datos vacíos. No fue posible inspeccionar su contenido desaparecido; la comprobación se basó en los montajes y el flujo oficial de arranque. Se retiraron únicamente esos dos binds. También se eliminaron del Compose las variables de aplicación que solo consumían los inicializadores; FastAPI sigue leyendo sus URLs desde el `.env` de raíz. No se recuperaron scripts ni se reinicializaron datos.

**Replicación:** el servidor conserva su identidad de clúster, condición de primario, `wal_level=replica`, `max_wal_senders=10`, ausencia de réplicas conectadas/slots y configuración síncrona vacía. Se conservó la red `poke-arena_default` y no se montó ni modificó `pokearena_pgreplica_data`. Esto acredita la topología observada, no una prueba de failover ni la configuración futura de una réplica.

### Credenciales y rutas

- En esta rama `.env.example` dejó de versionarse. `.env` en raíz es privado, ignorado por Git y debe tener permisos `0600`.
- Configuración central en `backend/src/shared/config.py`: el `.env` de raíz se localiza por la ruta del archivo, independientemente del directorio de ejecución. Variables del proceso tienen prioridad. `UPLOAD_DIR` relativo también se resuelve desde raíz, sin crear archivos al importar.
- `DATABASE_URL` y `MONGO_URL` son obligatorias, se excluyen de representaciones/serialización ordinaria y sus valores no aparecen en errores de validación. Se mantienen como cadenas por compatibilidad con los consumidores existentes, incluido Alembic, que no se modificó.
- La configuración de FastAPI requiere URLs explícitas. El aprovisionador legado `setup-dev` conserva valores fijos de desarrollo y queda fuera del procedimiento de CI-5. `DEBUG=false`, parámetros SQL ocultos y timeout de conexión configurable (`DB_CONNECT_TIMEOUT_SECONDS`, 1–60 segundos; valor inicial 5).
- La autorización posterior revocó la decisión de conservar las credenciales inválidas. Se renovó `poke_api_user` y se creó `poke_api_mongo`, con secretos aleatorios guardados únicamente en `.env`. Las URLs se habilitaron después de verificar autenticación y permisos; FastAPI usa esas cuentas, sin fallback administrativo. La contraseña administrativa no se rotó.
- La validación final utiliza los módulos oficiales y las URLs ordinarias de `.env`, sin inyectar administración: `poke_api_user`/`poke_api_mongo` autentican desde raíz y `backend/`. Solo se ejecutaron lecturas, consultas de permisos y ping; las pruebas no modificaron registros de negocio.
- Los healthchecks están aplicados y ambos servicios están `healthy`: SQL mediante TCP autenticado y Mongo mediante ping autenticado. La recreación corrigió las antiguas variables administrativas incongruentes con los usuarios persistidos. Las credenciales de aplicación ya no se propagan al entorno de los contenedores de bases.
- No imprimir `docker compose config` sin `--quiet`: la salida interpolada contiene secretos. Para inspecciones JSON, capturar en memoria y mostrar solo campos no sensibles. No copiar `.env` a documentación, incidencias o commits.

### Privilegios técnicos aplicados

Antes de rotar SQL se inspeccionaron sesiones, membresías y consumidores visibles: no había clientes usando `poke_api_user`, otros servicios activos dependientes ni membresías administrativas. La comprobación cubre los recursos observados, no clientes externos desconocidos. `pokearena_migrator` se conserva separado; no se ejecutó ninguna migración.

| Cuenta / recurso | Permisos |
|---|---|
| `poke_api_user`, base `pokearena_db` | CONNECT; USAGE del esquema public; sin CREATE de base/esquema ni membresía de migrador |
| `catalog_abilities` | SELECT |
| `catalog_card_code_counters` | SELECT, UPDATE |
| `catalog_cards`, `catalog_card_images`, `shared_idempotency_records`, `shared_outbox` | SELECT, INSERT, UPDATE |
| Atributos del rol SQL | NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS; sin DELETE/TRUNCATE en las seis tablas |
| `poke_api_mongo`, autenticación en `pokearena_catalog` | Rol local `pokearena_app_catalog`: find, insert, update y listIndexes solo sobre `cards_projection`; sin remove, drop, administración global ni acceso a otras bases |

Las escrituras futuras se autorizaron por permisos, pero no se ejercitaron con datos reales en 1A. La verificación consultó ACL y privilegios efectivos; comprobó además que Mongo rechaza lecturas de usuarios administrativos y de otra base. La proyección e índices existentes no cambiaron.

**GridFS permanece en 1C:** no se crearon buckets, colecciones ni permisos anticipados sobre archivos. Antes de ampliar el rol Mongo, acordar bucket y recursos concretos; una base distinta o permisos adicionales requieren autorización. No otorgar readWrite global para anticipar esa decisión.

### Respaldos y restauración verificados

Artefactos locales privados e ignorados: `docker-data/backups/1a-20261106/` (directorio `0700`, archivos `0600`). Contienen datos y hashes de contraseñas en el respaldo de roles: tratarlos como secretos. No subirlos a Git ni compartirlos sin protección. La copia está en el mismo host; no equivale a un respaldo externo contra pérdida del equipo.

- `postgres-globals.sql`: roles/globales SQL; un archivo custom `*.dump` por cada una de las cuatro bases.
- `mongo.archive.gz`: respaldo lógico MongoDB, incluyendo datos de aplicación, opciones, índices y usuarios administrativos según las herramientas del motor. No es una copia física completa de `/data/db` ni del contenido operativo de `local`.
- `source-before.json`, `source-after-backup.json`, `restored-verified.json` y `after-isolated-restart-verified.json`: huellas de filas/documentos y esquema.
- `manifest.json`: SHA-256 de artefactos y resultado de verificación. `operations-backup.py`, `operations-verify.py` y `operations-connections.py` conservan los comandos de diagnóstico de esta ejecución; son evidencia privada, no CLI estable del proyecto. No reejecutar el respaldo sin cambiar destino y nombres aislados.
- Las copias se restauraron con las **mismas imágenes locales** en contenedores `pokearena-1a-restore-postgres-20261106` y `pokearena-1a-restore-mongo-20261106`, sin red externa, puertos publicados ni montajes de volúmenes fuente. Se reiniciaron solo esos clones para comprobar persistencia.
- Clones y sus volúmenes `pokearena_1a_restore_pg_20261106`, `pokearena_1a_restore_mongo_20261106` y `pokearena_1a_restore_mongo_config_20261106` quedan conservados; los contenedores están detenidos. No se borró ningún volumen.
- Coincidieron conteos y huellas de todas las filas SQL, documentos/opciones/índices Mongo y esquema SQL normalizado. PostgreSQL reformatea casts equivalentes de arrays al restaurar: se normalizó exclusivamente esa representación para comparar el esquema; no se ejecutaron migraciones.
- Las huellas de las fuentes se comprobaron antes y después. No se observaron clientes de aplicación activos en SQL durante el inventario; no hay una instantánea distribuida entre ambos motores. Ante escrituras concurrentes futuras, acordar una ventana consistente de respaldo antes de cambios operativos.

Comandos utilizados (resumen sin secretos; scripts privados conservan argumentos exactos):

```bash
# Inventario de solo lectura:
docker ps -a
docker inspect pokearena-postgres pokearena-mongo
docker network inspect poke-arena_default
docker volume ls
# Respaldo SQL: pg_dumpall --globals-only y pg_dump -Fc -C para cada base.
# Mongo: mongodump --archive --gzip autenticado, secretos desde entorno.
# Restauración: psql de roles, pg_restore --exit-on-error, mongorestore --stopOnError.
# docker run --network none: solo clones nuevos, con volúmenes propios.
# docker restart / docker stop: clones durante restauración; las fuentes se recrearon
# posteriormente con autorización y el siguiente comando de alcance limitado:
docker compose -f docker-compose.yml up -d --no-deps --pull never --wait --wait-timeout 90 postgres mongo

# Validación de configuración sin imprimir secretos:
docker compose -f docker-compose.yml config --quiet
# Pruebas locales, sin escrituras a bases:
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/test_infrastructure_config.py -q
```

Las restauraciones se aplicaron únicamente a clones vacíos. La autorización posterior permitió recrear los dos contenedores originales, sin restaurar ni cambiar sus tablas o filas. Solo cambiaron las cuentas técnicas y ACL autorizadas. La comparación estructural final excluye ACL deliberadamente cambiadas y coincide con el clon restaurado.

### Validaciones y pendientes

**Exitosas:** respaldos SHA-256 íntegros y restauración previa validada; recreación autorizada con mismas imágenes y volúmenes; servicios healthy; identidad/configuración del primario preservadas; cuatro bases SQL y documentos/índices Mongo intactos; estructura SQL sin ACL igual al respaldo restaurado; usuarios técnicos sin administración; carga de `.env` desde raíz/backend; HTTP 200 en `/api/v1/health` con ambas bases connected; ocho pruebas de infraestructura; Compose y `git diff --check` válidos.

**Fuera de alcance / pendientes posteriores:** recuperación/verificación Alembic y 1B requieren autorización; GridFS y permisos de su bucket corresponden a 1C. No se validó instalación desde volúmenes vacíos, failover ni escrituras de negocio. Ruff/Mypy no están instalados en el entorno local y no se ejecutaron. La prueba HTTP usó la biblioteca estándar porque httpx, aunque declarado, tampoco está instalado; no se cambiaron dependencias.

Evidencia de cierre privada: `docker-data/backups/1a-20261106-completion/` conserva inventario antes/después, checks de identidad/replicación, privilegios sin contraseñas, huellas de datos, comando de recreación y scripts operativos sin secretos literales. Los respaldos originales son anteriores a la rotación: una restauración futura necesitará reconciliar las credenciales técnicas con el `.env` privado usando administración autorizada; no sobrescribir respaldos anteriores.

Para iniciar el backend ordinario desde raíz:

```bash
python3 manage.py dev-backend
# En otra terminal:
curl --fail http://127.0.0.1:8000/api/v1/health
```

El `.env` local ya tiene las cuentas verificadas. Un clon del repositorio no recibe secretos ni bases: debe completar su propia configuración y provisión autorizada; la plantilla vacía falla explícitamente.


## Entrega 1B.1 — Historial Alembic recuperado

Se recuperaron literalmente las revisiones 001–008 desde Git, sin incorporar 009 ni crear sucesoras. Las reconstrucciones independientes en bases vacías de una instancia PostgreSQL nueva alcanzaron `008_flex_card_img_dims` y coincidieron con la estructura activa: 12 tablas, 103 columnas, 50 restricciones y 27 índices. Las bases y los servicios originales no se modificaron.

Alembic usa `MigrationSettings` y `MIGRATION_DATABASE_URL` explícita, con rol separado y sin dependencia de MongoDB o de la URL de API. En esta fase se permiten solo destinos `pokearena_alembic_*`; el guard también verifica identidad real y ausencia de administración antes del DDL. La plantilla deja esa URL vacía. No usar las credenciales de aplicación para migraciones.

Los paths del INI son relativos a `%(here)s`; `path_separator=os` evita fragmentar la ruta del proyecto que contiene espacios. Por ello el mínimo de Alembic pasa a 1.16; la instalación usada es 1.20.1. No se añadieron librerías ni modelos.

```bash
# Desde raíz, sin conectar a bases:
backend/.venv/bin/python -m alembic -c backend/alembic.ini history
backend/.venv/bin/python -m alembic -c backend/alembic.ini heads
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/test_infrastructure_config.py backend/tests/test_alembic_recovery.py -q
```

La integración requiere dos URLs privadas `ALEMBIC_TEST_URL_A/B` hacia bases nuevas vacías de una instancia aislada; sin ellas se omite esa prueba y se informa. En la validación real pasaron las **24 pruebas**, incluida integración. No se limpia una base existente para repetir: crear destinos aislados nuevos. La instancia `pokearena-1b1-alembic-20261106` queda detenida, con volumen/red propios conservados; el puerto aleatorio publicado puede cambiar al iniciarla y las URLs de prueba deben releerse de Docker.

Procedencia, revisiones, comandos de reconstrucción, comparación y límites en [el informe 1B.1](backend/docs/contracts/ALEMBIC_RECOVERY_1B1.md). No se ejecutó Alembic sobre `pokearena_db`, ni stamp, downgrade, generación automática o migraciones sucesoras. No avanzar a 1B.2 sin autorización.

## Entrega 1B.2A — ORM y persistencia sin cambios de esquema

Se representan las seis tablas existentes con SQLAlchemy en los adaptadores y
propietarios compartidos. El dominio permanece puro; el repositorio usa la sesión
oficial y exige transacción del llamador. `catalogo_module.py` concentra la carga
aprobada con importlib para conservar las carpetas con guiones; no modifica
`sys.path` ni registra endpoints. Idempotencia y Outbox tienen un solo propietario.
La metadata es parcial: Alembic mantiene autogenerate bloqueado y no se cambió
ninguna revisión histórica ni el esquema original.

```bash
# Desde raíz, sin motores ni secretos privados (integraciones opt-in omitidas):
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q
```

Para integración se requieren tres bases nuevas de una instancia PostgreSQL 16
separada: dos vacías mediante `ALEMBIC_TEST_URL_A/B` y otra ya reconstruida con
001–008 mediante `ORM_TEST_DATABASE_URL`. Todas usan nombres `pokearena_alembic_*`
y rol separado no administrativo. Pasar URLs por entorno privado; nunca utilizar
las bases originales ni publicar credenciales. La suite no crea/limpia bases ni
restablece contadores; la prueba de commit conserva una fila sintética, por lo
que para repetir la ejecución completa se preparan nuevos destinos.

Validación real: **58 pruebas aprobadas, sin omisiones**; comparación ORM/SQL sin
diferencias y huellas de las cuatro bases originales intactas. Sin URLs opt-in:
27 aprobadas y 31 omitidas explícitamente. La instancia de pruebas queda detenida,
con recursos aislados conservados. No se añadieron dependencias; Ruff/Mypy siguen
sin estar instalados. Archivos, contratos, decisión de imports y sus limitaciones,
comandos y evidencia en [el informe 1B.2A](backend/docs/contracts/ORM_PERSISTENCE_1B2A.md).
No se implementó el flujo completo de Crear carta ni se avanzó a 1B.2B.

La corrección del Code Review usa `python manage.py lint` para revisar los módulos
por su nombre completo con la configuración de `backend/pyproject.toml`. Para
validar la persistencia sin ejecutar migraciones, define solo
`ORM_TEST_DATABASE_URL` hacia una copia aislada ya en la revisión 008. La suite
de corrección obtuvo **84 aprobadas y una omitida** en PostgreSQL 16. La omisión
corresponde a la reconstrucción histórica de Alembic.

## Entrega 1B.2B — Integridad de metadatos de imágenes

La cabeza local es `1b2b_card_image_integrity`. El ORM de 1B.2B se verifica
contra una base aislada en esa revisión mediante `ORM_TEST_DATABASE_URL`.
Para comprobar upgrade, rollback, downgrade y preservación de filas, proporcionar
también `SCHEMA_ALIGNMENT_TEST_URL` hacia una copia aislada descartable en 008.
La base original sigue en 008 y el guard de Alembic impide migrarla.
Consulta el [inventario, pruebas y plan de aplicación](backend/docs/contracts/SCHEMA_ALIGNMENT_1B2B.md).

## Entrega 1C — Medios en GridFS

El backend compone un procesador Pillow y un almacén PyMongo Async sobre la
conexión MongoDB existente. `MONGO_GRIDFS_BUCKET` selecciona el bucket y
su valor inicial es `card_assets`. El procesamiento acepta hasta 5 000 000
bytes por original, verifica la proporción 5:7 y genera WebP de 200 × 280.

Las pruebas unitarias funcionan sin bases. Las pruebas reales usan
`MONGO_GRIDFS_TEST_URL` hacia MongoDB 7 aislado y
`ORM_TEST_DATABASE_URL` hacia PostgreSQL aislado en 1B.2B.
El [informe 1C](backend/docs/contracts/GRIDFS_IMAGE_STORAGE_1C.md) documenta
la configuración, los permisos del bucket, las pruebas y la integración
pendiente en 1D.

## Entrega 1D — Servicio Crear Carta desde Python

`catalogo_module.crear_servicio_crear_carta()` compone el servicio con las
conexiones oficiales. El servicio requiere PostgreSQL aislado en
`1b2b_card_image_integrity` y MongoDB 7 autenticado sobre `card_assets`.
Las pruebas nuevas usan `ORM_TEST_DATABASE_URL` y `MONGO_GRIDFS_TEST_URL` hacia
destinos descartables. Los casos unitarios funcionan sin esas URLs.

El [informe 1D](backend/docs/contracts/CARD_CREATION_SERVICE_1D.md) incluye el
ejemplo de invocación, el protocolo de recuperación y los comandos para
reproducir las **152 pruebas aprobadas** con ambos motores. El despliegue sobre
las bases originales y la exposición por API requieren autorización separada.

## Entrega 1E — API Crear Carta

La ruta `POST /api/v1/content/cards` usa multipart, `Idempotency-Key` y una
sesión de plataforma con rol `PLATFORM_ADMIN`. El intercambio
`POST /api/v1/identity/google/session` recibe un ID token de Google y emite el
Bearer opaco. OpenAPI está disponible en `/docs`.

Para el ensayo aislado configura `GOOGLE_OAUTH_CLIENT_ID`,
`PLATFORM_ADMIN_GOOGLE_SUBJECTS` y `ALLOWED_ORIGINS`. La suite usa claves RSA
locales y URLs privadas de PostgreSQL 16 y MongoDB 7. Consulta el
[informe 1E](backend/docs/contracts/CARD_CREATION_API_1E.md) para ver los
comandos, permisos y condiciones de despliegue.

## Entrega 1F — Worker Outbox

Desde `backend/`, ejecutar `.venv/bin/python -m src.database.outbox_worker
--once` para procesar un lote o quitar `--once` para procesar continuamente.
Configurar las URLs privadas de la copia PostgreSQL y MongoDB antes de
ejecutarlo. El worker exige el índice UNIQUE de código en `cards_projection`.
El [informe 1F](backend/docs/contracts/CARD_CREATION_OUTBOX_1F.md) reúne los
parámetros, permisos, consultas y procedimiento de reconciliación.

## Entrega 1G — Backend Crear Carta integrado

El flujo aislado usa un administrador local aprovisionado explícitamente y
una sesión opaca revocable. La revisión `1g_local_master_admin` añade
identidad LOCAL sin cambiar las tablas de catálogo. El login local queda
desactivado por defecto mediante `IDENTITY_LOCAL_ENABLED=false`.

Consulta el [ensayo desde cero y plan de despliegue](backend/docs/contracts/CARD_CREATION_FINAL_1G.md)
y el [contrato HTTP para React](backend/docs/contracts/CARD_CREATION_FRONTEND_HANDOFF.md).
Google real, el despliegue original y el desarrollo frontend requieren
autorizaciones separadas.

## Colección inicial de jugadores

Las dos rutas existentes de login Google intentan provisionar el premio de un
jugador autenticado. El paquete se consulta con
`GET /api/v1/player/initial-pack` y se confirma con
`POST /api/v1/player/initial-pack/open`, usando el Bearer de Poké-Arena.
El entorno aislado requiere Alembic 014 y permiso de actualización en
`player_profiles.initial_pack_opened_at`. Consulta los
[estados y errores HTTP](backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md#15-integración-http-en-ci-3b). El backend está aprobado con observaciones para el onboarding React. Consulta el [informe CI-5E](backend/docs/contracts/CI_5_INFORME_CIERRE_BACKEND.md) para conocer la evidencia y el alcance de la integración.

## Catálogo de prueba CI-4

`backend/seed_cartas_ci4.py` genera 80 cartas, 20 por rareza, a partir de
`prueba/ip.png`. El lote predeterminado es `CI4-2026` y la semilla es `2026`.
Los nombres usan el prefijo `CI-SEED-<lote>--<rareza>-` y cada solicitud
conserva su clave de idempotencia al reanudar.

```bash
backend/.venv/bin/python -B backend/seed_cartas_ci4.py --solo-plan --seed 2026 --lote CI4-2026
backend/.venv/bin/python -B backend/seed_cartas_ci4.py --dry-run --seed 2026 --lote CI4-2026
backend/.venv/bin/python -B backend/seed_cartas_ci4.py --apply --confirm-isolated \
  --seed 2026 --lote CI4-2026 --backup-dir /ruta/privada/respaldo-ci4
```

`--solo-plan` valida la imagen y muestra el lote sin conectarse. El dry-run
es predeterminado y usa `DATABASE_URL`, `MONGO_URL`, `MONGO_DB` y
`CI4_PROJECTION_MONGO_URL` suministradas al proceso. La herramienta no carga
archivos de entorno. Para aplicar, suministrar además `CI4_ADMIN_BEARER` de
la misma base y mantener disponible el consumidor oficial de Outbox con su
credencial de proyección. El CLI consulta la proyección hasta `--espera`
segundos y reporta un lote incompleto si quedan pendientes.

El destino persistente permitido es PostgreSQL 014 en
`127.0.0.1:15433/pokearena_alembic_frontend_dev` y MongoDB en
`127.0.0.1:27029/pokearena_catalog_frontend_dev`. Apply en ese par requiere
autorización posterior al dry-run y respaldos generados por el operador:
`postgres.dump` en formato de `pg_restore` y un volcado MongoDB con gzip
bajo `mongo/pokearena_catalog_frontend_dev/`. El CLI lee los respaldos
localmente y no restaura datos. Los ensayos descartables usan los prefijos
`pokearena_alembic_ci4_test_` y `pokearena_outbox_ci4_test_` en otros puertos.
Consulta el [contrato CI-4](backend/docs/contracts/CI_4_CONTRATO_SEED_80_CARTAS.md).
