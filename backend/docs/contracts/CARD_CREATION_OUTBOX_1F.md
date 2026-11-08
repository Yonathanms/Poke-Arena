# Entrega 1F — Outbox y proyección de Crear Carta

**Dictamen de entrega** — APROBADO CON OBSERVACIONES para el alcance aislado.

## Diagnóstico

| Componente | Estado previo y decisión |
| --- | --- |
| Productor 1D | Reutilizable. Confirma `CardCreated` en la misma transacción que la carta, la imagen READY y la respuesta de idempotencia. El worker consume después del commit. |
| `shared_outbox` | Reutilizable sin DDL. PK por `id`, unicidad de `(aggregate_type, aggregate_id, aggregate_version)`, índices por tipo y estado e índice de reclamación por estado, próximo intento, vencimiento y fecha de creación. CHECK de intentos no negativos. |
| Lease | Reutilizable. `lease_token` y `lease_expires_at` permiten fencing. Outbox carece de columna de generación y de propietario. Un UUID nuevo por reclamación funciona como generación; el ID de proceso se registra en logs. |
| Worker oficial | Reutilizable con adaptación. El punto de entrada anterior tenía un lote vacío y escribía en `cards_catalog` por código. Se completa ese archivo y se usa `cards_projection`. |
| `cards_projection` | Colección histórica con índices `_id`, UNIQUE `code`, texto en `name`, `card_type` y `cost`. Se verificó el contrato sobre una réplica de los índices en MongoDB aislado. El worker exige el índice de código y conserva los demás. |
| Conexiones | Reutilizables. La composición toma la fábrica SQL y el cliente PyMongo Async oficiales. |
| Compatibilidad histórica | Algunos sobres o documentos históricos carecen de los campos 1D. Un evento incompatible se conserva en `FAILED`. Una colisión con un documento sin versión verificable requiere conciliación. |

Las revisiones 003 y 004 introdujeron el sobre y la recuperación. El esquema
no restringe los estados por CHECK. El consumidor aplica `PENDING`,
`PROCESSING`, `RETRY_PENDING`, `PROCESSED` y `FAILED`. PostgreSQL sigue
siendo fuente de verdad. El flujo de identidad de 1E permanece separado del
worker. La integración real con Google y el aprovisionamiento del administrador
maestro fuera de pruebas quedan fuera de esta fase.

## Evento y documento

El alcance del worker es `event_type = 'CardCreated'` y
`aggregate_type = 'card'`. Otros eventos conservan sus filas sin reclamarse.
La versión de esquema aceptada es **1**. El consumidor contrasta
`event_id`, `aggregate_id`, `aggregate_version`, `schema_version` y
`correlation_id` del sobre JSONB con sus columnas. Exige IDs UUID canónicos,
versión de agregado positiva y `created_at` con zona horaria. Actualmente 1D
usa el ID de carta como ID de evento, agregado y correlación.

El documento de `cards_projection` contiene:

| Campos | Origen |
| --- | --- |
| `_id`, `id`, `aggregate_version` | ID SQL estable y versión del agregado contrastados con el evento. |
| `code`, `name`, `card_type`, `rarity`, `cost`, `power` | Carta SQL de la misma versión. |
| `ability_id`, `ability_code` | Carta y habilidad SQL asociada. |
| `image_id`, `image_status` | Referencia y estado SQL. La imagen debe estar en `READY`. |

Los campos de negocio deben coincidir con el cuerpo 1D. La lectura de carta,
habilidad e imagen ocurre en una única consulta. Si la versión SQL cambió,
falta el agregado o el cuerpo discrepa, se conserva el evento para diagnóstico.
El worker no interpreta el estado SQL actual como si fuera una versión anterior.
El documento omite referencias internas GridFS, binarios, tokens y datos de
identidad.

## Reclamación, idempotencia y recuperación

1. El adaptador SQL comprueba la base de pruebas, el rol no superusuario y la
   revisión `1b2b_card_image_integrity`. En una transacción corta toma filas
   elegibles por `created_at, id` con `FOR UPDATE SKIP LOCKED`, aumenta intentos
   y asigna UUID y vencimiento con el reloj SQL. Solo se reclama el grupo
   que puede comenzar inmediatamente.
2. Tras el commit, valida el evento y lee su agregado. La lectura SQL termina
   antes de abrir operaciones MongoDB. Se intenta actualizar por `_id` solo
   con el mismo código y una versión numérica inferior. Si no hay documento,
   se intenta insertar. Ante un duplicado se lee por ID y, si procede, por
   código. Una versión igual y equivalente, o una versión superior del
   mismo ID y código, satisface la entrega. Versiones iguales discrepantes,
   códigos ajenos y versiones ilegibles quedan como incompatibles.
3. Mongo usa escrituras con mayoría y lecturas primarias con read concern
   de mayoría. La confirmación SQL posterior vuelve a comprobar el token,
   el estado y el vencimiento, ya bajo el lock de la fila. Una instancia
   obsoleta puede completar una escritura Mongo que ya inició, pero no puede
   retroceder la proyección ni confirmar con un lease vencido o reemplazado.
4. Si el commit SQL de confirmación es incierto, se deja decidir al estado
   persistido. Una fila confirmada queda `PROCESSED`. Una fila en
   `PROCESSING` vuelve a ser elegible al vencer. La entrega es
   **at-least-once** y la proyección conserva un documento por carta.

El worker reutiliza el patrón de exclusión de cola y la atomicidad de
una escritura Mongo por documento.
[PostgreSQL 16, cláusulas de bloqueo](https://www.postgresql.org/docs/16/sql-select.html#SQL-FOR-UPDATE-SHARE)
y [MongoDB, atomicidad de escrituras](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/).

| Situación | Resultado |
| --- | --- |
| Error temporal SQL/Mongo o respuesta Mongo no confirmada | `RETRY_PENDING` cuando la resolución SQL se confirma. Backoff `min(2**intento, tope)`, sin espera activa ni jitter, con límite de intentos. |
| Caída, reinicio o confirmación incierta | El estado durable y el vencimiento permiten recuperar. El replay conserva la proyección si ya existía. |
| Versión, cuerpo o agregado incompatible | `FAILED` con código sanitizado. Se conserva el sobre original. |
| Último intento sin éxito | `FAILED`. Si se pierde el lease en el último intento, la siguiente reclamación elegible lo conserva como `intentos_agotados`. Puede existir una escritura Mongo previa que deba verificarse. |

## Ejecución en aislamiento

Usar un entorno privado con `DATABASE_URL` hacia la copia PostgreSQL
`pokearena_alembic_*` y `MONGO_URL` / `MONGO_DB` hacia la copia Mongo
`pokearena_gridfs_test_*` o `pokearena_outbox_*`, ambos en loopback. El
rol SQL necesita SELECT en carta, habilidad, imagen, Outbox y revisión,
y UPDATE en Outbox. El rol Mongo necesita find, insert, update y
listIndexes sobre `cards_projection`. El índice UNIQUE `{code: 1}` debe
estar provisionado. El worker carece de permisos GridFS en el ensayo.

Desde la raíz, con las variables ya cargadas:

```bash
(cd backend && .venv/bin/python -m src.database.outbox_worker --once)
(cd backend && .venv/bin/python -m src.database.outbox_worker)
```

El modo continuo espera entre lotes. SIGTERM y SIGINT dejan terminar el grupo
ya reclamado y cierran los clientes. Un cierre forzado deja leases recuperables.
FastAPI funciona por separado.

| Variable | Valor por defecto |
| --- | --- |
| `OUTBOX_BATCH_SIZE` | 20 reclamaciones como máximo por ciclo |
| `OUTBOX_CONCURRENCY` | 4 operaciones simultáneas |
| `OUTBOX_POLL_SECONDS` | 5 segundos |
| `OUTBOX_LEASE_SECONDS` | 60 segundos |
| `OUTBOX_MAX_ATTEMPTS` | 8 |
| `OUTBOX_RETRY_MAX_SECONDS` | 300 segundos |

El lease debe superar el timeout de conexión. Usar los mismos límites en
workers que compartan una cola. Los logs registran IDs de evento, carta,
correlación y worker, intento, estado, duración y error sanitizado.

## Verificación y reconciliación

Consultas SQL de solo lectura para el consumidor:

```sql
SELECT status, count(*), min(created_at) AS mas_antiguo,
       count(*) FILTER (WHERE status = 'PROCESSING' AND lease_expires_at <= now()) AS vencidos
FROM shared_outbox
WHERE event_type = 'CardCreated' AND aggregate_type = 'card'
GROUP BY status;

SELECT c.id, c.code, c.version, i.state, o.id AS evento, o.status, o.sanitized_error
FROM catalog_cards c
JOIN catalog_card_images i ON i.id = c.image_id
LEFT JOIN shared_outbox o ON o.aggregate_id = c.id
    AND o.aggregate_type = 'card' AND o.event_type = 'CardCreated'
WHERE i.state = 'READY';
```

En MongoDB, inspeccionar los índices y contrastar por ID SQL.

```javascript
db.cards_projection.getIndexes()
db.cards_projection.findOne({_id: "<id SQL>"}, {
  code: 1, aggregate_version: 1, image_id: 1, image_status: 1
})
```

Comparar el conjunto SQL READY contra Mongo por ID y versión. Una carta sin
documento o con versión inferior requiere revisar primero su evento y la
compatibilidad del snapshot. Si existe un `CardCreated` compatible de la
misma versión, se puede autorizar el replay de esa fila individual después
de detener consumidores y drenar escrituras previas. Respaldar la fila,
confirmar que no hay lease activo ni colisión de código, reabrirla a `PENDING`
con intentos y fechas operativas reiniciados, y ejecutar un lote. Conservar
payload, IDs y versiones. Verificar documento y estado `PROCESSED`.
Si falta el evento, la versión difiere, el documento existente carece de
versión o hay colisión con otro ID, hace falta una reparación explícita
basada en el primario. Un replay ordinario conserva los documentos
incompatibles.

## Archivos

- `database/outbox_worker.py` — CLI, modos y señales.
- `catalogo_module.py` — composición y carga explícita.
- `domain/proyeccion_carta.py`, `ports/proyeccion_ports.py` y
  `services/proyeccion_service.py` — contrato, validación y orquestación.
- `adapters/sql_outbox_repository.py` y `adapters/mongo_card_projection.py`
  — lease, snapshot, confirmación y escritura versionada.
- `shared/config.py` — límites y tiempos.
- `backend/tests/test_outbox_worker.py` — regresiones y fallos controlados.
- `README.md`, `AGENTS.md` y contrato general — alcance y comandos.

## Validación

Desde raíz, con las URLs de prueba descritas en [1E](CARD_CREATION_API_1E.md) y una
`MONGO_OUTBOX_TEST_URL` autenticada como `projection_test` en la copia Mongo:

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade 1b2b_card_image_integrity
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -p no:cacheprovider backend/tests -q -rs
backend/.venv/bin/python manage.py lint
backend/.venv/bin/python -m ruff check backend/tests/test_outbox_worker.py
(cd backend && .venv/bin/python -m mypy --config-file pyproject.toml -m tests.test_zz_outbox_worker)
backend/.venv/bin/python -m compileall -q backend/src backend/tests
git diff --check
```

Se usó PostgreSQL 16.15 y MongoDB 7.0.45 en contenedores efímeros con
volúmenes en memoria. En la copia SQL se aplicó 1B.2B y se mantuvieron
destinos separados para las regresiones Alembic. Repetir con PostgreSQL y MongoDB
nuevos como conjunto. En una repetición intermedia, el worker rechazó los
códigos SQL reiniciados porque la copia Mongo conservaba las proyecciones
de otra corrida. La cuenta de proyección se verificó sin acceso a GridFS.

| Validación | Resultado |
| --- | --- |
| Suite final con motores aislados | **219 aprobadas, 0 omitidas, 0 fallidas**. Incluye 194 regresiones y 25 pruebas de 1F. |
| Pruebas nuevas sin motores | 13 aprobadas. Se omiten 12 al faltar infraestructura. |
| Integración real | 12 casos. HTTP 201 con el worker detenido, CLI de lote y continuo con SIGTERM, reclamación concurrente, fila bloqueada, fencing, error Mongo, reinicio, commit incierto antes y después, proyección monotónica, colisiones, versiones y estados incompatibles. |
| Calidad | Ruff, Mypy sobre 42 módulos y el archivo de pruebas, compilación y `git diff --check` aprobados. |

Las pruebas inyectan fallos de conexión y pérdida de confirmación, sin
simular un failover de clúster. Los eventos históricos ya procesados quedan
fuera del consumo normal y requieren revisión antes de un replay.

## Condiciones para 1G

Validar el backend integrado, la provisión controlada del administrador
maestro y los permisos de destino. Para un entorno original se requieren
autorizaciones separadas para migración, privilegios, reconciliación de
documentos históricos y levantamiento de los guards de aislamiento.
Mantener Google real y frontend fuera de 1F. Revisar tiempos de lease y
backlog con el volumen de operación previsto.
