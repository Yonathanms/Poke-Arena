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
* Genera `.env` en raíz si no existe (permisos `0600` en macOS/Linux). La plantilla deja secretos y URLs vacíos: deben completarse de forma privada con credenciales verificadas; copiarla no inicializa usuarios.
* Crea el entorno virtual de Python (`backend/.venv`) e instala los paquetes necesarios.
* Descarga e instala los paquetes de Node.js en `frontend/`.

*(Si en algún momento solo quieres regenerar el archivo de configuración sin reinstalar librerías, puedes ejecutar: `python manage.py env`).*

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

---

## Comandos de Utilidad (`manage.py`)

Todos estos comandos se ejecutan desde la raíz del proyecto (`Poke-Arena/`):

| Comando | Descripción |
| :--- | :--- |
| **`python manage.py install`** | Genera el `.env` e instala dependencias de Backend y Frontend. |
| **`python manage.py env`** | Genera exclusivamente el archivo `.env` a partir de `.env.example`. |
| **`python manage.py dbs`** | Enciende PostgreSQL y MongoDB en Docker. |
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
├── .env.example                    # Plantilla oficial de variables de entorno
│
├── frontend/                       # APLICACIÓN WEB (React + TypeScript + Tailwind)
│   └── src/
│       ├── 📁 web-admin/           # Portal de Administradores (Gestión de Catálogo)
│       ├── 📁 web-player/          # Portal de Jugadores (Colección y Partidas)
│       └── 📁 portal-b2b/          # Portal de Organizaciones B2B (Torneos)
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
            └── 📁 motor-juego/     # Motor de batalla puro y máquina de estados
```

> **Regla de oro para crear código nuevo:**  
> Cada submódulo (ejemplo: `catalogo/gestion-cartas`) contiene 5 carpetas de arquitectura hexagonal:
> 1. `controllers/`: Endpoints HTTP y validación con Pydantic DTOs.
> 2. `services/`: Reglas del negocio y casos de uso.
> 3. `domain/`: Modelos de la base de datos (tablas).
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

- `.env.example` no contiene contraseñas ni URLs con credenciales. `.env` en raíz es privado, ignorado por Git y creado localmente con permisos `0600`.
- Configuración central en `backend/src/shared/config.py`: el `.env` de raíz se localiza por la ruta del archivo, independientemente del directorio de ejecución. Variables del proceso tienen prioridad. `UPLOAD_DIR` relativo también se resuelve desde raíz, sin crear archivos al importar.
- `DATABASE_URL` y `MONGO_URL` son obligatorias, se excluyen de representaciones/serialización ordinaria y sus valores no aparecen en errores de validación. Se mantienen como cadenas por compatibilidad con los consumidores existentes, incluido Alembic, que no se modificó.
- No hay credenciales por defecto en código. `DEBUG=false`, parámetros SQL ocultos y timeout de conexión configurable (`DB_CONNECT_TIMEOUT_SECONDS`, 1–60 segundos; valor inicial 5).
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
