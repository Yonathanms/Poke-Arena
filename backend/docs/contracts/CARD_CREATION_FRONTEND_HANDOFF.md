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
