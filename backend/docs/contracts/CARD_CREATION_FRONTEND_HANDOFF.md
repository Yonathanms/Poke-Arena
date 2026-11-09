# Contrato para React — Crear Carta

La API de 1G se validó en un entorno aislado. El cliente solo usa HTTPS y
las rutas de la API. Durante el ensayo local se permite HTTP en loopback.
Configurar `ALLOWED_ORIGINS` con el origen exacto de React, por ejemplo
`http://localhost:5173`. Los preflights aceptan `Authorization`,
`Content-Type` e `Idempotency-Key` para los métodos autorizados.

## Sesión administrativa

Enviar JSON a `POST /api/v1/identity/local/session` con `username` y
`password`. El usuario es el maestro provisionado explícitamente por el
operador. La respuesta 201 contiene `access_token`, `token_type: "Bearer"`,
`expires_in` en segundos, `user_id` y `role: "PLATFORM_ADMIN"`. La duración
predeterminada es 900 segundos. La ruta solo está disponible con el opt-in
de 1G. Google real se incorpora en otra etapa mediante el proveedor
existente.

Enviar `Authorization: Bearer <access_token>` en cada solicitud protegida.
Al cerrar sesión, `DELETE /api/v1/identity/session` con el mismo header
devuelve 204 y revoca el token. Tratar 401 como sesión ausente, inválida o
vencida. Un 403 indica que la sesión actual carece del rol requerido. Para
429 de login respetar `Retry-After`. Mantener el Bearer fuera de URLs, logs
y reportes de errores.

## Formulario y habilidades

`GET /api/v1/content/abilities` requiere la misma autorización y devuelve
un array de objetos `{ "code": "HAB-000", "name": "Sin Habilidad" }` ordenados
por código. Mostrar `name` y enviar `code` como `ability_code`. La selección
es obligatoria y se valida de nuevo en la creación.

`POST /api/v1/content/cards` requiere `multipart/form-data`, Bearer e
`Idempotency-Key`. Cada campo se envía una vez. El navegador debe producir
el `Content-Type` con boundary al serializar el formulario.

| Campo | Valor |
| --- | --- |
| `name` | Nombre de 1 a 100 caracteres tras recortar espacios externos. |
| `cost` | Entero de 0 a 10. |
| `power` | Entero de −20 a 20. |
| `card_type` | `FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC`. |
| `rarity` | `COMUN`, `POCO_COMUN`, `RARA`, `LEGENDARIA`. |
| `ability_code` | Código existente de la lista administrativa. |
| `image` | Un original PNG, JPEG o WebP. |

Para previsualizar antes de enviar, el cliente puede leer el archivo local.
El servidor valida los bytes, admite hasta **5 000 000** bytes y exige
proporción exacta **5:7** y mínimo **600 × 840** tras orientación. Genera un
WebP de **200 × 280**. La API de creación devuelve identificadores. La
lectura de imágenes almacenadas queda pendiente de un endpoint autorizado.

Ejemplo de una solicitud multipart, con el archivo como parte binaria:

```text
POST /api/v1/content/cards
Authorization: Bearer <token>
Idempotency-Key: <uuid generado por el cliente>

name=Guardiana
cost=2
power=-5
card_type=LUC
rarity=RARA
ability_code=HAB-000
image=<contenido binario de guardiana.png>
```

Ejemplo de respuesta 201:

```json
{
  "id": "03de590e-b414-403e-88a0-d3a8c1c37e86",
  "code": "PKA-LUC-001",
  "operation_id": "03de590e-b414-403e-88a0-d3a8c1c37e86",
  "image_id": "03de590e-b414-403e-88a0-d3a8c1c37e86",
  "image_status": "READY"
}
```

La clave tiene entre 1 y 128 caracteres ASCII visibles, sin coma.
Generar una clave por operación y conservarla durante los reintentos con
los mismos datos y bytes. Un replay confirmado devuelve el mismo 201 y el
mismo cuerpo. Un envío intencionalmente nuevo usa otra clave. El 201
confirma PostgreSQL y ambos archivos verificados. La proyección MongoDB
puede aparecer después, cuando el worker procese el evento.

## Errores y correlación

Las rutas devuelven `application/problem+json` con `type`, `title`,
`status`, `detail`, `code` y `correlation_id`. Leer el código estable
para decidir cómo presentar el error. Mostrar el ID de correlación si
se necesita diagnosticar una solicitud. El servidor lo incluye también
en `X-Correlation-ID` y expone ese header por CORS.

| HTTP | Comportamiento |
| --- | --- |
| 401 / 403 | Pedir una sesión nueva o informar que la sesión carece de permiso. |
| 404 | Actualizar la selección si la habilidad dejó de existir. En login local puede indicar que la ruta está deshabilitada. |
| 409 | `conflicto_idempotencia` señala datos distintos. `en_curso` permite repetir con la misma clave. Los códigos de reserva, resultado, medios o compensación requieren conciliación. |
| 413 / 415 / 422 | Mostrar el límite, el tipo de solicitud esperado o el error de campos e imagen. |
| 429 | Esperar los segundos de `Retry-After` en login. |
| 500 / 503 | Conservar la clave. Si el código es `commit_incierto`, repetir la misma operación para consultar el resultado. |

La especificación generada está en `/openapi.json` y `/docs`.

## Buscar Carta — contrato IA-1

`GET /api/v1/content/cards` conserva el Bearer de Poké-Arena, los parámetros
`q`, `tipo`, `rareza`, `limite` y `pagina`, y la respuesta
`items`, `total`, `pagina`, `limite` y `total_paginas`.
El tamaño predeterminado es 15 y el máximo es 100. Los resultados se
ordenan por código e ID. Una página fuera de rango conserva el total y
devuelve `items: []`. Una consulta sin coincidencias tiene `total: 0`
y `total_paginas: 1`.

El filtro `rareza` acepta `COMUN`, `POCO_COMUN`, `RARA` y `LEGENDARIA`.
Los valores anteriores `INFRECUENTE` y `EPICA` reciben `422`. El texto se
busca como fragmento literal sin distinguir mayúsculas. Los filtros de
texto, tipo y rareza se intersectan. La búsqueda y el detalle leen
`cards_projection`. Una proyección inaccesible devuelve
`503 catalogo_no_disponible`. Un detalle inexistente devuelve `404`.

## Operación aislada de Crear Carta — configuración IA-2

Validar primero la asignación de puertos de los contenedores aislados y
los destinos efectivos de cada proceso. La API y el worker deben usar
`127.0.0.1:15433/pokearena_alembic_frontend_dev` en revisión
`014_identity_account_immutable` con `orm_media_test` y MongoDB
`127.0.0.1:27029/pokearena_catalog_frontend_dev`. Proporcionar las
credenciales existentes por el canal privado del operador.

| Proceso | Usuario en su propio `MONGO_URL` | Privilegios MongoDB |
| --- | --- | --- |
| FastAPI | `media_test` | `find`, `insert`, `remove`, `listIndexes` y `createIndex` en `card_assets.files` y `card_assets.chunks`. IA-2 añadió solo `find` en `cards_projection`. |
| Outbox | `projection_test` | Conservar `find`, `insert`, `update` y `listIndexes` en `cards_projection`. |

En ambos procesos, usar `MONGO_DB=pokearena_catalog_frontend_dev`, la base
como `authSource` y `directConnection=true`. La API usa el bucket
`card_assets`. El worker del aislado persistente valida además
`ENVIRONMENT=development` y el par exacto de destinos. El cliente Mongo
compartido se configura por proceso, por lo que la separación usa las
variables existentes. En PostgreSQL se conservan las ACL vigentes.

IA-2 aplicó y comprobó este permiso en el aislado persistente. El rol
`catalog_projection_reader` se concedió solo a `media_test`. Para
reproducir el aprovisionamiento en otro aislado con autorización
específica, usar una sesión administrativa de `mongosh` conectada al
destino verificado. Si el rol ya existe, inspeccionar sus privilegios
antes de concederlo.

```javascript
const catalogo = db.getSiblingDB("pokearena_catalog_frontend_dev");
const lector = "catalog_projection_reader";
if (!catalogo.getUser("media_test") || catalogo.getRole(lector)) {
  throw new Error("Revisar el usuario o el rol existente antes de continuar");
}
catalogo.createRole({
  role: lector,
  privileges: [{
    resource: {db: catalogo.getName(), collection: "cards_projection"},
    actions: ["find"]
  }],
  roles: []
});
catalogo.grantRolesToUser("media_test", [{role: lector, db: catalogo.getName()}]);
```

Verificar con `connectionStatus` autenticado en cada proceso y con un
`GET /api/v1/content/cards?limite=100` en la API. El rol de FastAPI
requiere lectura de la proyección, sin privilegios de escritura sobre
ella ni de enumeración global de colecciones.

### Arranque de los procesos

1. Comprobar con `docker inspect` los mapeos de los contenedores
   `pokearena-pg-frontend-dev` y `pokearena-mongo-frontend-dev`. Comparar
   host, puerto, base y usuario de las URLs efectivas con la tabla anterior.
   Verificar mediante conexiones autenticadas el usuario y la revisión
   de PostgreSQL y los roles efectivos de MongoDB. Si algo difiere,
   detener el arranque.
2. En la terminal de la API, inyectar de forma privada `DATABASE_URL`
   de `orm_media_test`, `MONGO_URL` de `media_test` y
   `GOOGLE_OAUTH_CLIENT_ID` vigente, correspondiente al cliente del
   frontend. Conservar la configuración de autorización Google validada.
   Usar `ENVIRONMENT=development`, `DEBUG=false`,
   `MONGO_DB=pokearena_catalog_frontend_dev` y
   `MONGO_GRIDFS_BUCKET=card_assets`. Desde `backend/`, arrancar y
   comprobar `/api/v1/health` y una búsqueda autenticada:

   ```sh
   .venv/bin/python -B -m uvicorn src.main:app --host 127.0.0.1 --port 8000
   ```

3. En una terminal independiente, inyectar el mismo destino PostgreSQL y
   su propio `MONGO_URL` con `projection_test`. Usar el mismo
   `MONGO_DB`, `ENVIRONMENT=development` y `DEBUG=false`. El worker
   valida los destinos y el índice único de código. Desde `backend/`:

   ```sh
   .venv/bin/python -B -m src.database.outbox_worker
   ```

   El arranque del worker procesa eventos. Para un diagnóstico de solo
   lectura, limitarse a la validación de configuración, roles e índice.
   Evitar mostrar las URLs completas al comprobar los destinos.

### Recuperación de reservas existentes

Las dos reservas diagnosticadas siguen en `RETRY_PENDING`, con dos
intentos cada una. Antes de recuperar una, verificar por su ID de
operación en solo lectura el estado de `catalog_card_images`, la
respuesta de `shared_idempotency_records` y la existencia de la carta y
su evento Outbox. Comparar internamente el actor y la clave de la reserva
con los datos originales, sin mostrarlos en el informe. Para una
recuperación autorizada, conservar el mismo administrador, la misma
`Idempotency-Key`, los mismos campos normalizados y los mismos bytes del
archivo original. El servidor verifica la huella y reutiliza la reserva
y las referencias GridFS. Si ya existe un resultado confirmado, devuelve
el mismo `201`. Una huella distinta con la misma clave devuelve
`409 conflicto_idempotencia`. Si falta la clave o el archivo original,
dejar la reserva pendiente para conciliación.
