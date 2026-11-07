# Entrega 1D — Servicio de aplicación Crear Carta

**Dictamen de cierre técnico: APROBADO CON OBSERVACIONES para el entorno aislado.** La carrera de compensación y los errores de lectura idempotente quedaron corregidos. La reanudación administrativa de un borrado incierto y la habilitación del entorno original conservan requisitos operativos explícitos.

## Compatibilidad y decisiones

| Componente | Uso en 1D |
| --- | --- |
| Catálogo SQL | Los seis mapeos existentes conservan tablas, FKs, PK `VARCHAR(36)` y restricciones. El repositorio oficial consulta la habilidad, comprueba su ruta de evolución y bloquea el contador por tipo con `SELECT FOR UPDATE`. |
| Idempotencia | La unicidad existente de actor, operación y clave arbitra la reserva. Se conserva la operación histórica `POST:/api/v1/content/cards` y su huella SHA-256 canónica de campos más el SHA-256 del original. Solo se recorta el nombre, igual que en el contrato histórico. |
| Reserva | El par de respuesta SQL nulo, `resource_id = id` y la fila pendiente de imagen con el mismo ID representan una reserva 1D. Un UUID identifica operación, carta futura, fila de imagen y evento en sus tablas respectivas. Las dos referencias `gridfs:<ObjectId>` se conservan antes del primer upload. |
| Medios | El procesador y el almacén 1C validan PNG/JPEG/WebP, el límite de 5 000 000 bytes, la orientación EXIF, 600 × 840 mínimo y la proporción exacta 5:7. La miniatura es WebP 200 × 280. La verificación vuelve a leer los archivos y contrasta bytes, formato, dimensiones y hashes medidos. SQL conserva el hash del original y los metadatos de ambos archivos. |
| Outbox | `CardCreated` conserva el sobre versionado existente y enlaza el ID del evento y la correlación con la operación. El payload lleva datos de carta, habilidad e imagen verificada. La forma del payload para consumo futuro de la proyección se debe acordar en 1F. |
| Esquema | La revisión `1b2b_card_image_integrity` basta. El adaptador verifica el nombre de base aislada `pokearena_alembic_*` y la revisión antes de autorizar el flujo. |

La historia 2.1.1 se contrastó con el contrato del backend y el diseño histórico en
`8a9e309:docs/design/content/create-card.md`. El ADR histórico de ese commit
(`docs/adr/ADR-002-create-card-images.md`) describe un flujo con archivos locales
y procesamiento posterior. Para el alcance 1D se eligió preparar y verificar
medios en la misma invocación antes de insertar la carta. PostgreSQL conserva
evidencia durable aun si esa invocación termina sin resultado. Se mantiene el
Outbox, la proyección existente y la compatibilidad de alcance y huella de claves
históricas. La política de lectura y conciliación se detalla más abajo.

## Flujo y límites transaccionales

1. Validar campos y calcular la huella. Adquirir un lock de sesión PostgreSQL por alcance con `pg_try_advisory_lock`. Si está ocupado, devolver `en_curso`. La sesión se conserva hasta completar la invocación. La conexión se invalida si existe incertidumbre al adquirir o liberar el lock.
2. Leer la clave en una transacción corta. Reproducir el resultado confirmado o rechazar una huella diferente. Consultar la habilidad existente y validar destino, autorreferencia y ciclos con una CTE recursiva. Comprobar capacidad del contador sin consumirlo.
3. Procesar el archivo fuera de la transacción SQL. En otro `BEGIN`, confirmar la reserva `PENDING` y ambas referencias o registrar el intento sobre la reserva previa. Solo entonces escribir en GridFS y recuperar el par para verificarlo.
4. En el `BEGIN` final, volver a leer idempotencia y habilidad, bloquear el contador del tipo, asignar el código `PKA-<TIPO>-NNN` y confirmar incremento, imagen `READY`, carta, Outbox y resultado idempotente. El repositorio usa la transacción del llamador. El servicio devuelve éxito después de que el adaptador confirme esta transacción.

PostgreSQL conserva el lock de sesión a través de transacciones cortas. Durante
Pillow y GridFS la sesión está sin transacción ni lock de fila. La prueba de
concurrencia comprueba `pg_locks` y `pg_stat_activity` desde otra conexión.
Referencias [bloqueos de sesión PostgreSQL 16](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS)
y [detección de ciclos con CTE](https://www.postgresql.org/docs/16/queries-with.html#QUERIES-WITH-CYCLE).

## Fallos y recuperación

| Situación | Efecto y recuperación |
| --- | --- |
| Datos, habilidad o imagen inicial inválidos | Sin reserva, carta, Outbox ni incremento. |
| Otra ejecución para la misma clave | `en_curso`. Repetir con el mismo contenido. Una vez disponible la clave, una huella distinta produce `conflicto_idempotencia`. |
| Fallo de subida o verificación | La reserva conserva ambas referencias. Cuando se puede confirmar el diagnóstico, queda en `RETRY_PENDING` con categoría sanitizada. Repetir sobre los mismos IDs. |
| Fallo conocido de carta o Outbox | Rollback del incremento, carta, READY, evento y respuesta. Los archivos verificados se conservan para el siguiente intento. |
| Commit de resultado incierto | `commit_incierto`. Repetir la misma solicitud. La lectura SQL bajo el lock resuelve si hay resultado confirmado o si se debe completar la reserva. Se conservan ambos archivos. |
| Cancelación o interrupción | La reserva confirmada identifica los dos archivos incluso desde otra instancia. El reintento necesita el mismo original y los mismos datos. |
| Chunk huérfano o archivo corrupto | Un operador de confianza confirma que las escrituras anteriores de la clave han terminado y llama a `compensar(actor, clave)`. SQL conserva el marcador `compensacion_pendiente` antes de borrar y bloquea nuevos intentos hasta confirmar ambos borrados. El proceso de reanudación se detalla a continuación. |

## Endurecimiento de la compensación

Con una sesión PostgreSQL estable, el lock de sesión por actor, operación y
clave excluye otras creaciones y limpiezas de la misma reserva. Solicitudes
independientes tienen IDs GridFS propios. Si se pierde la sesión mientras un
comando MongoDB está pendiente, el servidor libera el lock SQL, pero MongoDB
puede terminar ese comando. En la creación automática, dos intentos pueden
alcanzar los mismos IDs después de ese fallo. Ambos usan el contenido de la
misma huella. El adaptador exige igualdad exacta para reutilizar archivos y
GridFS tiene unicidad por ID y por `(files_id, n)`. La conexión perdida no
puede confirmar la carta. Un conflicto de escritura o un par parcial requiere
otro intento o recuperación administrativa. [Índices de GridFS](https://www.mongodb.com/docs/manual/core/gridfs/#gridfs-indexes).

El caso destructivo estaba en `compensar`. La lectura SQL que autorizaba el
borrado podía quedar obsoleta al perderse el lock. En el control negativo se
pausó el primer borrado, se terminó la sesión real con
`pg_terminate_backend` y una nueva instancia confirmó una carta mientras el
borrado seguía activo. El código corregido aplica esta secuencia:

1. Bajo el lock de sesión, leer el primario y comprobar que la reserva es
   recuperable, que no hay carta confirmada y que los IDs no aparecen en
   otra fila de imagen. Confirmar `RETRY_PENDING` con
   `sanitized_error = 'compensacion_pendiente'` en la misma transacción.
2. Ejecutar ambos borrados por ID fuera de la transacción SQL. Una nueva
   creación o una limpieza ordinaria encuentra el marcador y devuelve
   `compensacion_pendiente`, aunque la sesión que lo confirmó haya caído.
   El adaptador también impide registrar un intento o pasar a READY mientras
   esté marcado. Ante un commit incierto del marcador se devuelve
   `commit_incierto` antes de enviar cualquier borrado.
3. Retirar el marcador solo después de ambos borrados confirmados. La reserva
   conserva sus IDs para el siguiente intento. Si el borrado se interrumpe o
   su confirmación es incierta, el marcador queda persistido. Tras leer el
   primario, el operador debe verificar que acabaron todos los escritores y
   el limpiador previo, incluidos sus comandos pendientes en MongoDB. Solo
   entonces puede usar `compensar(actor, clave, reanudar=True)`. Si no puede
   demostrarlo, debe mantener la reserva bloqueada. El marcador tampoco
   tiene expiración automática.

Se reutiliza la columna de diagnóstico de la fila pendiente. El servicio
decide cuándo bloquear y reanudar, el adaptador SQL impone la condición y
el adaptador GridFS conserva su API de borrado por ID. El lock protege una
sesión. El marcador protege el intervalo destructivo incluso si se pierde esa
sesión. PostgreSQL y MongoDB no pueden verificar conjuntamente que un comando
anterior terminó. Por eso el drenaje sigue siendo una precondición administrativa
al iniciar una limpieza y, especialmente, al retomar una interrumpida. Las
nuevas llamadas ordinarias quedan bloqueadas desde SQL durante la limpieza.

## Idempotencia histórica y conciliación

La implementación histórica de Crear Carta reservaba por actor, operación
`POST:/api/v1/content/cards` y clave. Su resultado 201 tenía un ID de registro
distinto de `resource_id`, un resumen anidado de habilidad, URLs y disponibilidad,
y podía indicar `PENDING` o no tener imagen. Carecía de `contract: "1D"` y de
`image_id`. Esas filas pueden coincidir por alcance y huella en el mismo primario.
La migración 003 también identifica registros anteriores como `__legacy__`,
con operación igual al endpoint y sin huella verificable. En el código histórico
revisado, el consumidor de ese mecanismo genérico era Crear ubicación. Ese
alcance no se reasigna a actores de Crear Carta.

| Lectura del primario | Política |
| --- | --- |
| Misma huella, resultado 201 de 1D, código del tipo solicitado y relación SQL coherente con imagen READY | Reproducir el resultado confirmado. |
| Misma huella, resultado confirmado histórico o incoherente | Devolver `resultado_incompatible`. Se incluye JSONB que no es objeto, aunque el par SQL estado/cuerpo sea válido. Conservar fila y recursos. |
| Respuesta SQL nula y reserva de 1D identificable | Continuar con los mismos IDs, salvo si existe una compensación pendiente. |
| Respuesta SQL nula sin reserva segura, o con una carta ya asociada | Devolver `reserva_incierta`. Conservar las filas y no escribir en GridFS. |
| Huella distinta bajo el mismo alcance | Devolver `conflicto_idempotencia`. La forma del cuerpo no altera esa decisión. |
| El primario aún no ha confirmado el resultado de un commit | Devolver `commit_incierto` y volver a consultar la clave en el primario. Conservar los archivos. |

Para conciliar, el operador localiza el registro por alcance y documenta en
modo de solo lectura su estado, `resource_id`, huella y formato. Contrasta
carta, vínculo de imagen y Outbox con esos identificadores. Si las referencias
son GridFS, verifica existencia e integridad de ambos archivos. Si son locales,
conserva los archivos y su procedencia para el plan de transición. Solo se puede
habilitar una respuesta equivalente tras demostrar identidad, resultado y
disponibilidad con evidencia persistente. La conciliación requiere aprobación
explícita de cualquier corrección. Usar otra clave o borrar la fila original
puede crear un duplicado y no resuelve la discrepancia.

## Uso desde Python

Desde `backend/`, con el engine configurado para una copia PostgreSQL autorizada
en 1B.2B y una conexión autenticada a GridFS aislado, usar la composición oficial.
El actor representa un principal previamente autenticado por el llamador. La
identidad permanece separada de los datos de carta.

```python
from src.modules.catalogo import catalogo_module as catalogo

app = catalogo.aplicacion_cartas
datos = catalogo.dominio_cartas.DatosCarta("Guardiana", 2, 5, "AGU", "RARA", "HAB-000")
servicio = catalogo.crear_servicio_crear_carta()
resultado = await servicio.ejecutar(
    app.ActorCreacion(principal_id),
    app.SolicitudCrearCarta(clave_idempotencia, datos, original_bytes),
)
```

## Archivos y responsabilidades

| Archivo | Responsabilidad |
| --- | --- |
| `catalogo_module.py` | Composición Python, carga dinámica centralizada y clientes oficiales. |
| `domain/carta_model.py` | Validación de atributos y formato de código. |
| `domain/imagen_model.py`, `adapters/imagen_carta_adapter.py` | Función SHA-256 compartida por solicitud y procesamiento. |
| `ports/cartas_ports.py`, `adapters/sql_carta_repository.py` | Lectura de ruta de evolución y actualización transaccional de contador. |
| `ports/creacion_ports.py`, `adapters/sql_creacion_carta.py` | Reserva, idempotencia, Outbox, lock de sesión y transacciones explícitas sobre las seis tablas existentes. |
| `services/cartas_service.py` | Tipos de aplicación, orquestación, resultado y errores recuperables. |
| `backend/tests/test_service_crear_carta.py` | Reglas, concurrencia, fallos y recuperación con evidencia de SQL y GridFS. |
| `AGENTS.md`, `README.md`, `CARD_CREATION_BACKEND.md` | Fase autorizada, ejecución y relación con los contratos previos. |

## Validación reproducible

Las pruebas usaron PostgreSQL **16.15** y MongoDB **7.0.45** efímeros, con puertos
loopback aleatorios y datos en tmpfs. Se copió el clúster de pruebas detenido
a un archivo temporal y se montó ese archivo como solo lectura durante el
arranque. Se prepararon una base para el ORM y 1D, otra en 008 para validar
la sucesora y dos vacías para reconstruir el historial. El rol SQL de prueba
carecía de privilegios administrativos y el rol Mongo solo podía operar sobre
`card_assets.files` y `card_assets.chunks`. Al terminar se retiraron ambos
contenedores y los archivos temporales con credenciales. Se verificó el estado
y la fecha de arranque de los dos originales y de la instancia aislada fuente.
Los dos originales seguían saludables.

Desde raíz y con las herramientas del entorno de desarrollo, inyectar por entorno
privado las URLs `MIGRATION_DATABASE_URL`, `ORM_TEST_DATABASE_URL`,
`SCHEMA_ALIGNMENT_TEST_URL`, `ALEMBIC_TEST_URL_A/B` y `MONGO_GRIDFS_TEST_URL`.
Las bases de integración se preparan de nuevo para repetir la suite, pues
algunas pruebas comprueban commits reales.

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade 1b2b_card_image_integrity
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -p no:cacheprovider backend/tests -q -rs
backend/.venv/bin/python -m coverage run --source=backend/src -m pytest -c backend/pyproject.toml -p no:cacheprovider backend/tests -q -rs
backend/.venv/bin/python -m coverage report
backend/.venv/bin/python manage.py lint
backend/.venv/bin/python -m ruff check backend/tests/test_service_crear_carta.py
(cd backend && .venv/bin/python -m mypy --config-file pyproject.toml -m tests.test_service_crear_carta)
backend/.venv/bin/python -m compileall -q backend/src backend/tests
git diff --check
```

| Validación | Resultado |
| --- | --- |
| Suite completa con ambos motores | **152 aprobadas, 0 omitidas**. Incluye 116 regresiones de fases anteriores y 36 casos de 1D, siete incorporados en el cierre técnico. |
| Casos nuevos | 14 unitarios, 1 con PostgreSQL real para la ruta de evolución y 21 de integración PostgreSQL + GridFS. Las regresiones incluyen 7 pruebas reales del adaptador GridFS de 1C, una de ellas con contraste SQL. |
| Escenarios inyectados | Subida original y parcial de miniatura, corrupción real de un chunk, borrado parcial, CHECK de carta, PK duplicada de Outbox, fallo de respuesta antes y después de commit, cancelación y recuperación por otra instancia. |
| Regresiones de cierre | Terminación real de sesión durante un borrado, commit incierto del marcador sin borrar, discrepancia entre respuesta 1D y carta, y respuestas JSONB históricas de tipo objeto, array, cadena y nulo, además de reserva no identificable. |
| Controles negativos | Dos fallos esperados en una copia del código anterior. La creación se confirmó mientras el borrado seguía activo y el array JSONB produjo `AttributeError`. La copia de trabajo conservó los cambios corregidos. |
| Suite sin URLs aisladas | **77 aprobadas, 75 omitidas**. |
| Calidad | Ruff, Mypy estricto (26 módulos de backend y el módulo nuevo de pruebas), compilación y `git diff --check` aprobados. |
| Cobertura de líneas | 91% del código medido de `backend/src`, 94% de `cartas_service.py` y 89% de `sql_creacion_carta.py`. Se terminó una sesión PostgreSQL real para probar el intercalado. La pérdida de respuesta del driver y la espera en MongoDB se simularon de forma controlada, sin probar un failover de clúster. |

## Preparación de despliegue

1. Obtener autorización específica del destino, del cambio de esquema y de
   los permisos. Registrar nombre, versión, revisión y rol efectivo del
   primario. Preparar un respaldo consistente de PostgreSQL y de los medios
   existentes. Restaurar ambos en destinos independientes y comprobar
   referencias e integridad antes de abrir la ventana de cambio.
2. Sobre la restauración en 008, inventariar filas que no satisfacen 1B.2B.
   Los dos predicados siguientes deben devolver cero filas. Si hay
   incompatibilidades, conservar los datos y acordar una corrección separada.

   ```sql
   SELECT count(*) FROM catalog_card_images
   WHERE (width >= 600 AND height >= 840 AND width::bigint * 7 = height::bigint * 5)
         IS NOT TRUE;

   SELECT count(*) FROM catalog_card_images
   WHERE state = 'READY'
     AND (thumbnail_storage_key IS NOT NULL AND thumbnail_format = 'WEBP'
          AND thumbnail_byte_size > 0 AND thumbnail_width = 200 AND thumbnail_height = 280)
         IS NOT TRUE;
   ```

3. Ensayar en la copia el comando de upgrade de la sección de validación
   con el rol separado de Alembic. Confirmar la revisión y que los dos CHECK
   están validados. Comparar conteos, IDs, contadores y referencias antes y
   después. El guard actual de Alembic y el del caso de uso permiten solo
   bases aisladas `pokearena_alembic_*`. Para un despliegue original hace falta
   una habilitación de destino revisada aparte. El ensayo no justifica
   renombrar bases, usar `stamp` ni saltarse los guards.
4. En el entorno aprobado, verificar la lectura de `alembic_version` y
   conservar el resto de privilegios SQL por tabla. En MongoDB 7, habilitar
   solo el bucket configurado por `MONGO_DB` y `MONGO_GRIDFS_BUCKET=card_assets`.
   El rol de aplicación necesita `find`, `insert`, `remove`, `listIndexes`
   y `createIndex` en `card_assets.files` y `card_assets.chunks`. Validar con
   conexión autenticada, índices GridFS y una prueba de par desechable en la
   copia. Usar los ejemplos de [permisos de 1C](GRIDFS_IMAGE_STORAGE_1C.md).
5. Ejecutar las pruebas de creación, replay y fallo parcial en el entorno
   de ensayo con la misma configuración prevista. Abrir la ventana del
   entorno original solo después de verificar backups, precondiciones y
   permisos. Si falla una verificación posterior, mantener el flujo
   deshabilitado y conciliar las reservas y referencias antes de elegir
   entre continuar o recuperar el respaldo. PostgreSQL y GridFS deben
   reconciliarse como conjunto.

## Observaciones y requisitos para 1E

- El lock consume una conexión PostgreSQL por operación activa y requiere
  sesiones estables. Hay que dimensionar conexiones y plazos al definir los
  límites HTTP. Los futuros escritores de habilidades deben preservar las
  invariantes del grafo cuando modifiquen relaciones.
- La limpieza interrumpida permanece bloqueada hasta que un operador verifique
  el drenaje. La retención de reservas y la conciliación de resultados
  históricos quedan fuera del cierre técnico. No se modificaron ni se
  inventariaron las filas originales para esta revisión.
- 1E debe obtener el actor de un contexto autenticado, definir autorización y
  traducir a HTTP los errores tipados, incluidos `compensacion_pendiente`,
  `reserva_incierta` y `resultado_incompatible`. La compensación permanece
  administrativa. La publicación y el consumo de eventos de proyección
  corresponden a una fase posterior.
