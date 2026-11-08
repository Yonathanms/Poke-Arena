# 1B.2B — Adecuación del esquema para Crear Carta

La auditoría de `pokearena_db` se hizo en una transacción de solo lectura. La
revisión registrada y la cabeza local inicial eran `008_flex_card_img_dims`.
El esquema contiene 12 tablas, 103 columnas, 50 restricciones y 27 índices.
Se inspeccionaron también la función y el trigger de inmutabilidad del código.

| Requisito | Evidencia observada en 008 | Clasificación | Decisión |
|---|---|---|---|
| Cartas, código, tipos, rareza, costo, poder, versión y relaciones | PK `VARCHAR(36)`, código único e inmutable, `CHECK` de tipo, rango, prefijo y número, habilidad obligatoria, imagen opcional y única | Compatible | Conservar la tabla y el trigger. La publicación y la validación previa a la creación son del caso de uso. |
| Habilidades reutilizables | `HAB-000` existe sin efecto. FK de carta obligatoria y sin UNIQUE. Destino de evolución opcional | Compatible | Conservar. Verificar ciclos y autorreferencias en el caso de uso cuando corresponda. |
| Original PNG/JPEG/WebP y hasta 5 MB decimales | Formato limitado, tamaño 1–5 000 000, hash hexadecimal y referencia obligatoria | Compatible | Conservar. El procesamiento debe comprobar los bytes y la correspondencia de los metadatos. |
| Original de al menos 600 × 840 y 5:7 exacto | 008 admite 300 × 420 y tolerancia de aspecto | Incompatible | Sustituir el CHECK de aspecto y usar aritmética `bigint` en la expresión para evitar desbordamiento. Las columnas siguen siendo `integer`. |
| Miniatura completa para `READY` | La clave y el formato se exigen, pero `CHECK` acepta `UNKNOWN` cuando tamaño, ancho o alto son NULL | Incompatible | Hacer obligatorios esos tres valores en el CHECK condicional de `READY`. Conservar la nulabilidad mientras no esté lista. |
| Estados, reintentos y recuperación de imágenes | Estado enumerado por CHECK, contadores no negativos, lease, próxima ejecución e índices de trabajo | Compatible | Conservar. |
| Contadores y unicidad del código | Seis filas, rango 0–999, PK por tipo y código único en cartas | Compatible | Conservar valores. La asignación futura controla el agotamiento y usa el bloqueo existente. |
| Idempotencia | UNIQUE por actor, operación y clave, hash y par de respuesta | Compatible | Reutilizar la restricción para arbitrar concurrencia. El caso de uso decidirá repetición frente a conflicto. |
| Outbox | Evento, agregado, versión, JSONB, estado, lease, intentos y unicidad por agregado/versión | Compatible | Reutilizar en la transacción del futuro caso de uso. |
| Resolución de referencias y archivos en GridFS | Las claves SQL son cadenas. El formato de referencia y el bucket siguen pendientes | Por confirmar | Resolver en la etapa autorizada para medios. |

### Inventario de las seis tablas

En el inventario siguiente, `?` indica columna nullable. Las restantes son
`NOT NULL`. Las PK y los UNIQUE tienen sus propios índices.

- **`catalog_cards`**. `id varchar(36)` PK `catalog_cards_pkey1`, `code varchar(30)` UNIQUE, `name varchar(100)`, `cost` y `power smallint`, `card_type varchar(3)`, `rarity varchar(20)`, `ability_id varchar(36)`, `image_id varchar(36)?` UNIQUE, `version bigint DEFAULT 1`, `created_at timestamptz`. Las FK a habilidad e imagen son `ON DELETE RESTRICT`. Los CHECK cubren nombre recortado de 1–100 caracteres, costo 0–10, poder −20–20, seis tipos, cuatro rarezas, código acorde con tipo y rango 001–999, y versión ≥1. Índices explícitos por tipo y rareza. `trg_catalog_cards_code_immutable` llama a `prevent_catalog_card_code_change()` antes de actualizar el código. Se observó una carta.
- **`catalog_abilities`**. `id varchar(36)` PK, `code varchar(7)` UNIQUE, `name varchar(100)`, `ability_type varchar(30)`, `description varchar(500) DEFAULT ''`, `params jsonb`, `has_effect boolean DEFAULT true`, `evolution_target_card_id varchar(36)?` con FK `ON DELETE RESTRICT` a cartas. CHECK de formato `HAB-NNN` y de la combinación reservada para `HAB-000`. Se observó una habilidad, la opción sin efecto.
- **`catalog_card_images`**. `id varchar(36)` PK, `original_storage_key varchar(512)`, `original_sha256 varchar(64)`, `image_format varchar(10)`, `byte_size`, `width` y `height integer`. Miniatura nullable con `thumbnail_storage_key varchar(512)`, `thumbnail_format varchar(10)` y `thumbnail_byte_size`, `thumbnail_width`, `thumbnail_height integer`. `state varchar(20) DEFAULT 'PENDING'`, `attempts` y `generation integer DEFAULT 0`, `lease_token varchar(36)?`, `lease_expires_at` y `next_attempt_at timestamptz?`, `sanitized_error varchar(500)?`, `created_at` y `updated_at timestamptz`. CHECK de estado (`PENDING`, `PROCESSING`, `RETRY_PENDING`, `READY`, `FAILED`), intentos, generación, hash, formatos, tamaño, dimensiones positivas, aspecto y miniatura para `READY`. Índices `ix_catalog_card_images_work` y `ix_catalog_card_images_claim`. Cero filas y cero incompatibilidades de datos observadas.
- **`catalog_card_code_counters`**. `card_type varchar(3)` PK, `last_value integer DEFAULT 0`. CHECK de tipo y rango 0–999. `PLA=1` coincide con el máximo asignado. Los otros cinco tipos están en cero y carecen de códigos asignados.
- **`shared_idempotency_records`**. `id varchar(36)` PK, `idempotency_key varchar(128)`, `endpoint varchar(200)`, `response_status integer?`, `response_body jsonb?`, `created_at timestamptz`, `actor_id varchar(128)`, `operation varchar(200)`, `request_hash varchar(64)`, `resource_id varchar(36)?`. UNIQUE `uq_shared_idempotency_scope` y CHECK que exige ambos campos de respuesta nulos o ambos presentes. Una fila observada.
- **`shared_outbox`**. `id varchar(36)` PK, `event_type varchar(60)`, `payload jsonb`, `status varchar(20)`, `created_at timestamptz`, `processed_at timestamptz?`, `aggregate_type varchar(60)`, `aggregate_id varchar(36)`, `aggregate_version` y `schema_version integer`, `correlation_id varchar(36)?`, `attempts integer`, `next_attempt_at timestamptz?`, `lease_token varchar(36)?`, `lease_expires_at timestamptz?`, `sanitized_error varchar(500)?`. UNIQUE por tipo e ID de agregado y versión, CHECK de intentos ≥0, índices por tipo de evento, estado y reclamación. Una fila observada.

Las otras cinco tablas auditadas carecen de triggers de negocio y mantienen sus
defaults actuales. Identidad, ubicaciones, legado y conciliación histórica quedan
fuera de los cambios. SQL valida metadatos. La existencia y decodificación de
archivos, orientación, proporción real y generación de la miniatura requieren
procesamiento del binario.

## Implementación y validación

La única sucesora es `1b2b_card_image_integrity`, hija directa de
`008_flex_card_img_dims`. Reemplaza `ck_catalog_card_images_aspect` y
`ck_catalog_card_images_ready_thumbnail` bajo sus nombres actuales. Los dos
CHECK se validan al crearlos. PostgreSQL ejecuta el DDL en una transacción y
retiene el bloqueo de la tabla durante los reemplazos. Si una fila incumple
algún CHECK, se revierte la revisión completa. La migración carece de DML.

El ORM refleja los dos predicados nuevos. Los puertos, el repositorio, la
configuración de Alembic y el manifiesto de hashes de 001–008 permanecen
iguales. La cabeza local es única. La antigua revisión 009 sigue excluida.

### Proporción exacta y validación de la miniatura en 1C

Para dimensiones positivas, `width / height = 5 / 7` equivale exactamente a
`7 × width = 5 × height`. La migración y el ORM convierten ambas dimensiones a
`bigint` antes de multiplicar. El mayor producto posible para las columnas
`integer` es `7 × 2 147 483 647 = 15 032 385 529`, dentro del rango de `bigint`.
La comparación usa enteros, sin división, redondeo ni tolerancia. Las pruebas
aceptan 600 × 840 y un múltiplo grande de 5:7, y rechazan 601 × 840.

En 1C, la integración con GridFS deberá verificar una miniatura de prueba sobre
el contenido recuperado y contrastarlo con SQL. Estas son las comprobaciones
pendientes una vez aprobados el bucket y el formato de referencias:

1. Resolver la referencia SQL al archivo correcto y recuperar el binario
   completo. Comprobar también que se puede recuperar el original asociado.
2. Decodificar el binario de la miniatura con límites de recursos. Confirmar
   por contenido que es WebP legible y que mide exactamente 200 × 280 píxeles.
   Rechazar contenido corrupto, truncado o de otro formato aunque su nombre o
   sus metadatos declaren WebP.
3. Comprobar que la cantidad de bytes recuperados es positiva e igual a
   `thumbnail_byte_size`. Contrastar formato y dimensiones decodificados con
   `thumbnail_format`, `thumbnail_width` y `thumbnail_height`.
4. Probar referencias faltantes, archivos ilegibles y metadatos discordantes
   en el entorno aislado. La verificación de ambos binarios debe completarse
   antes de habilitar `READY` en el futuro flujo. SQL sigue siendo la fuente
   autoritativa de metadatos.

Se usó PostgreSQL 16 efímero con almacenamiento independiente. Un destino se
restauró con `pg_dump` y `pg_restore` a partir de una lectura de la base original.
El segundo partió de una plantilla aislada ya en 008. Se aplicó exclusivamente
la sucesora. Los roles aislados de ORM y migración eran distintos. El rol ORM
de pruebas tuvo permisos para probar restricciones sobre habilidades y leer
la versión en su base descartable. Los permisos originales no se ampliaron.

| Validación | Resultado |
|---|---|
| Integridad de 001–008 y cadena Alembic | Ocho hashes coinciden y hay una sola cabeza en 1B.2B. |
| Dos fallos esperados de upgrade | Un original de 300 × 420 y una miniatura `READY` con tamaño NULL se admiten en 008. Cada uno bloquea el upgrade y conserva revisión, esquema y huellas de filas. |
| Upgrade, downgrade y reaplicación en la copia representativa | Solo cambian los dos CHECK y la versión registrada. Coinciden las huellas y cantidades de filas de todas las tablas de datos, incluidos IDs, códigos y contadores. Ambos CHECK quedan validados. |
| ORM y restricciones | Se comprobó el esquema objetivo, las FK, los defaults y los índices. Se probaron originales válidos e inválidos, `READY` completo, tres campos NULL, miniatura de ancho incorrecto y aritmética sin overflow. |
| Regresión de cartas, transacciones, concurrencia, idempotencia y Outbox | Aprobada. El contador acepta 999, rechaza 1000 y conserva el valor tras el rollback del intento. |
| Pytest | 92 aprobadas y una omitida. La única omisión corresponde a reconstruir dos bases vacías aplicando las revisiones históricas, incluidas las de identidad. |
| Ruff y Mypy | Backend, sucesora y archivos de pruebas afectados aprobados. |

La única fila ajustada por la prueba fue su imagen sintética, tras verificar
cada fallo. El downgrade restaura los CHECK exactos de 008 y se probó con datos
representativos. Puede fallar atómicamente si las dimensiones de filas nuevas
desbordan la aritmética `integer` de 008. También vuelve a permitir metadatos
que el contrato objetivo rechaza.

Para repetir la validación, preparar dos destinos desechables `pokearena_alembic_*`
en PostgreSQL 16, ambos en 008. Proporcionar por entorno privado una URL de
migración para el destino ORM, una URL de aplicación aislada en
`ORM_TEST_DATABASE_URL` y una URL de migración para la copia representativa en
`SCHEMA_ALIGNMENT_TEST_URL`. La prueba de alineación deja esa copia en la cabeza
objetivo. Para repetirla se necesita otra copia en 008.

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini heads
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade 1b2b_card_image_integrity
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q -rs
backend/.venv/bin/python manage.py lint
git diff --check
```

## Aplicación futura a la base original

1. Obtener autorización específica para el destino original y revisar el guard
   de Alembic en esa operación. Actualmente el guard rechaza `pokearena_db`.
2. Confirmar la revisión 008 y verificar un respaldo reciente con restauración.
   Repetir la comprobación de filas incompatibles y revisar el tamaño de la tabla
   y la ventana para el bloqueo exclusivo que necesita `ALTER TABLE`.
3. Abortar si hay originales por debajo de 600 × 840, proporciones distintas de
   `CAST(width AS bigint) * 7 = CAST(height AS bigint) * 5`, o filas `READY`
   sin clave, formato WebP, tamaño positivo y dimensiones 200 × 280. Acordar el
   tratamiento de las filas afectadas antes de reintentar. Preservar sus datos.
4. Pausar las escrituras afectadas, aplicar la sucesora con el rol de migración
   autorizado y verificar la revisión, los CHECK validados y las huellas de
   filas y contadores. Desplegar después el código que declara el esquema nuevo
   y reanudar el tráfico una vez confirmada la compatibilidad.

**Pendiente de autorización posterior.** Aplicación a `pokearena_db`, contrato
GridFS y comportamiento del caso de uso. La base original sigue en 008.
