# Entrega 1C — Subsistema de imágenes y GridFS

La entrega implementa procesamiento local, almacenamiento por ID y verificación
de pares. PostgreSQL conserva las referencias y el estado autoritativo. La
operación Crear Carta y la transición de estado corresponden a 1D.

## Arquitectura y archivos

| Archivo | Responsabilidad |
|---|---|
| `gestion-cartas/domain/imagen_model.py` | Representaciones de binarios, metadatos e IDs. El repr omite los bytes. |
| `gestion-cartas/ports/imagen_ports.py` | Interfaces y errores de procesamiento y almacenamiento. |
| `gestion-cartas/adapters/imagen_carta_adapter.py` | Validación, orientación visual, miniatura y verificación mediante Pillow. |
| `gestion-cartas/adapters/mongo_carta_repository.py` | Reserva, escritura, lectura, verificación y borrado exacto de IDs mediante GridFS. |
| `catalogo/catalogo_module.py` | Composición y carga dinámica de los adaptadores oficiales. |
| `database/mongodb/connection.py`, `main.py` | Cliente compartido de PyMongo Async por loop y cierre asíncrono en el lifespan existente. |
| `shared/config.py`, `.env.example`, `backend/pyproject.toml` | Bucket configurable, plantilla de entorno y dependencia explícita de PyMongo. |
| `test_image_processing.py`, `test_gridfs_image_storage.py` | Pruebas locales, integración autenticada y contraste SQL/GridFS. |

La conexión oficial reemplaza Motor por `AsyncMongoClient` de
`pymongo>=4.13,<5`. El endpoint de salud conserva su ping y oculta detalles
internos del fallo Mongo. El consumidor del worker sigue siendo compatible
mediante `await update_one`. El worker queda inactivo. La composición emplea
`AsyncGridFSBucket` sobre el cliente del loop actual. La validación de esta
entrega usó Python 3.12, PyMongo 4.19.0, Pillow 13.0.0 y MongoDB 7.0.45.

Referencias oficiales de [migración a PyMongo Async](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/),
[GridFS asíncrono](https://pymongo.readthedocs.io/en/4.13.0/api/gridfs/asynchronous/grid_file.html)
y [protecciones de Pillow](https://pillow.readthedocs.io/en/stable/handbook/security.html).

## Procesamiento e integridad

`procesar(original: bytes)` recibe un solo archivo. El límite del contrato
funcional es **5 000 000 bytes** decimales, inclusivo. La lectura en GridFS
usa el mismo límite por binario. Para PNG, JPEG y WebP, Pillow identifica
el formato, verifica la estructura y vuelve a abrir el archivo para
decodificarlo. Se rechazan entradas animadas o multipágina y cabeceras
que superan 20 000 000 píxeles antes de decodificar. Las protecciones
globales de Pillow se conservan.

Tras aplicar la orientación EXIF se exige mínimo 600 × 840 y
`7 × ancho = 5 × alto` con enteros. El original permanece byte por byte
idéntico a la entrada y su SHA-256 se calcula sobre esos bytes. Sus
dimensiones SQL corresponden a la orientación visual. La miniatura se
reduce a 200 × 280 con LANCZOS y se codifica en WebP con calidad 85 y
método 4. RGB y RGBA conservan el canal alfa cuando existe. La miniatura
omite EXIF, XMP e ICC. Los perfiles de color de origen se conservan en
el original. La miniatura se interpreta como RGB estándar, con posible
variación cromática en imágenes con perfiles especiales.

El procesador reabre la salida y comprueba la decodificación, el formato
real y las dimensiones. `verificar_par` recupera ambos binarios completos
por sus IDs y contrasta longitud real, dimensiones, formato y checksum
esperado. La decodificación de verificación se ejecuta fuera del event
loop. El SHA-256 del original viene de `original_sha256` en SQL. SQL carece
de hash de miniatura. Su verificación desde una fila SQL comprueba tamaño,
formato y dimensiones. El hash calculado puede comprobarse mientras el
llamador conserva los metadatos de la operación.

## Referencias, reintentos y compensación

`MONGO_GRIDFS_BUCKET` vale `card_assets` por defecto en la base indicada
por `MONGO_DB`. El diseño de despliegue usa `pokearena_catalog` y sus
volúmenes persistentes actuales. Las pruebas usaron una base desechable.
Los campos `original_storage_key` y `thumbnail_storage_key` reciben
`gridfs:<ObjectId hexadecimal minúsculo>`. Cada referencia mide 31
caracteres frente al límite SQL de 512. El bucket y la base deben permanecer
estables mientras existan referencias. Las rutas históricas se rechazan
como referencias GridFS. Mongo conserva solo los documentos técnicos del
bucket en `card_assets.files` y `card_assets.chunks`.

| Operación | Contrato |
|---|---|
| `reservar()` | Asigna dos IDs distintos sin hacer I/O. El llamador los retiene antes de escribir y asegura propiedad exclusiva de la operación. |
| `guardar_par(refs, imagen)` | Recibe los bytes procesados y devuelve referencias y metadatos cuando se confirman ambos archivos. Un archivo completo en un ID reservado se reutiliza si los bytes coinciden. |
| `recuperar(ref)` | Lee por ObjectId y verifica límites y longitud de GridFS. |
| `verificar_par(registro)` | Contrasta ambos binarios con los metadatos de la operación o de la fila SQL. |
| `eliminar(ref)` | Borra por ID exacto, incluidos chunks huérfanos. Admite repetir el borrado del mismo ID. Requiere que el llamador confirme propiedad y ausencia de escritura activa o de referencias confirmadas. |

La validación inválida y el error de codificación ocurren antes del guardado.
Un fallo durante el guardado produce `ErrorGuardadoPar` con ambos IDs
reservados, los confirmados y la causa clasificada. Un ID sin confirmar puede
estar ausente, parcialmente escrito o completo. Un reintento con los mismos
IDs y bytes comprueba lo que ya se guardó. Un archivo con otros bytes se
reporta como inconsistencia y se conserva. La limpieza de chunks huérfanos
requiere confirmar primero que la operación anterior terminó y que el ID
pertenece a esa operación. Los fallos de borrado se propagan con su carácter
reintentable. Una cancelación conserva la capacidad de reconciliar mediante
los IDs que el llamador obtuvo antes de escribir.

Los fallos de conexión y timeout se clasifican como reintentables. Permisos
denegados, referencias inválidas, archivos ausentes y corrupción conservan
diagnósticos diferenciados sin reproducir detalles del driver. El adaptador
carece de reintento automático a nivel de par. El dueño de la operación
decide cuándo repetir o compensar. Repetir el procesamiento con otra
versión del codificador puede producir bytes distintos y provocar un
conflicto de reintento. En 1D se deberá coordinar la retención o recuperación
de los bytes, la persistencia de los IDs antes de escribir, la idempotencia,
la exclusión entre operaciones y la decisión de marcar READY.

## Permisos y despliegue futuro

La inspección de solo lectura confirmó que `poke_api_mongo` dispone de
`find`, `insert`, `update` y `listIndexes` sobre `cards_projection`.
El bucket necesita un rol adicional en la misma base. El rol aislado con
`find`, `insert`, `remove`, `listIndexes` y `createIndex` en las dos
colecciones del bucket permitió el CRUD y la creación inicial de los
índices. La cuenta aislada recibió código 13 al intentar leer la proyección.

Tras autorización explícita, un administrador conectado de forma segura
puede revisar o crear un rol acotado y asignarlo de forma aditiva.
Ejemplo para el bucket por defecto en el entorno original:

```javascript
const media = db.getSiblingDB("pokearena_catalog");
const role = "pokearena_gridfs_card_assets";
const actions = ["find", "insert", "remove", "listIndexes", "createIndex"];
if (!media.getRole(role)) {
  media.createRole({
    role,
    privileges: ["card_assets.files", "card_assets.chunks"].map(collection => ({
      resource: { db: media.getName(), collection },
      actions
    })),
    roles: []
  });
}
printjson(media.getRole(role, { showPrivileges: true }));
```

Una vez comprobado que el rol contiene exactamente los permisos previstos,
ejecutar en la misma sesión administrativa:

```javascript
media.grantRolesToUser("poke_api_mongo", [{ role, db: media.getName() }]);
```

Validar los permisos con un par de prueba autorizado y los índices de
GridFS `filename/uploadDate` y `files_id/n` único. Usar el mismo usuario
de aplicación y conservar su rol de proyección. Antes de integrar el
estado SQL de producción se requiere la aplicación autorizada de 1B.2B.
La base original sigue en 008 y la configuración de almacenamiento y
contenedores originales se preservó.

## Reproducción de la validación

Con las dependencias declaradas instaladas y URLs privadas de pruebas
configuradas, ejecutar desde la raíz:

```bash
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q -rs
backend/.venv/bin/python manage.py lint
git diff --check
```

`MONGO_GRIDFS_TEST_URL` debe apuntar a un puerto loopback aislado de
MongoDB 7 con base `pokearena_gridfs_test_*` y usuario `media_test` con
el rol de bucket descrito. Para el contraste SQL, configurar
`ORM_TEST_DATABASE_URL` con una base desechable en
`1b2b_card_image_integrity` y una cuenta de pruebas distinta del migrador.
Las regresiones históricas opt-in usan dos bases vacías
(`ALEMBIC_TEST_URL_A/B`) y la prueba de sucesora una copia en 008
(`SCHEMA_ALIGNMENT_TEST_URL`). Todas se preparan exclusivamente en
instancias aisladas. Las URLs se transmiten en el entorno del proceso.
La fixture Mongo usa `loop_scope="function"` para usar y cerrar el cliente
en el mismo loop que la prueba. El mínimo de pytest-asyncio es 0.24.

## Resultados

| Grupo | Resultado |
|---|---|
| Procesamiento sin bases | 16 aprobadas. Incluye formatos, límites, truncamiento, EXIF, animación, transparencia, verificación de hash y fallo de codificación. |
| MongoDB 7.0.45 real autenticado | 6 aprobadas. Incluye original de 5 MB repartido en chunks, descarga por ID, índices y permisos, corrupción, longitud excesiva, borrado y fallos parciales controlados. |
| MongoDB + PostgreSQL en 1B.2B | 1 aprobada. El contraste se hizo a partir de los campos ORM leídos, incluido el hash SQL del original. El par incompleto no superó la verificación. |
| Regresiones 1A a 1B.2B | 93 aprobadas. Las migraciones históricas y sucesora se ejecutaron en destinos PostgreSQL descartables. |
| Total | **116 aprobadas y cero omitidas**. |

El entorno de prueba usa almacenamiento efímero independiente. La prueba
demuestra persistencia y lectura real durante la vida del servidor. La
persistencia tras reinicio del entorno original corresponde a sus
volúmenes verificados en 1A. Los resultados de lint, tipado y compilación
se comprobaron sobre el backend y los archivos Python de 1C.
