# Entrega 1E — API y seguridad de Crear Carta

**Dictamen: APROBADO CON OBSERVACIONES para el entorno aislado.** La validación
criptográfica se ejecutó con claves RSA locales. La prueba con Google real y la
habilitación de los permisos del entorno original requieren trabajo autorizado
por separado.

## Diagnóstico y alcance

| Responsabilidad | Diagnóstico | Resolución |
| --- | --- | --- |
| FastAPI y conexiones | Salud, CORS y cierre de clientes existentes. | Reutilizados con composición explícita de routers. Salud conserva su contrato y omite detalles de errores PostgreSQL. |
| Crear Carta | Servicio 1D validado con las transacciones, los errores tipados y las garantías de idempotencia. | Reutilizado íntegramente. El controlador solo adapta multipart, credencial, resultado y errores. |
| Identidad | Directorios oficiales vacíos. El histórico de Git `8a9e309` define un intercambio Google por sesión de plataforma. Las revisiones 005 y 006 definen `identity_users` y `identity_sessions`. | Adaptación mínima en las rutas oficiales. Reutiliza tablas, sujetos, roles y formato de token opaco. El proveedor TEST histórico no se acepta. |
| Seguridad y errores | Carpetas transversales definidas, sin implementación activa. | Bearer de plataforma y errores RFC 7807 compartidos. |
| Google real y entorno original | Se necesitan configuración de Google, aprobación del destino y permisos. | Validación local con firma real y JWKS simulado. Despliegue y prueba externa pendientes. |

La historia 2.1.1 se contrastó con el contrato v1.3 y el diseño en
`8a9e309:docs/design/content/create-card.md`. El OpenAPI histórico en
`8a9e309:docs/openapi/content-create-card.yaml` fija `/content/cards` y
`8a9e309:docs/openapi/identity-google-session.yaml` fija el intercambio. La
imagen obligatoria y el estado READY se rigen por los contratos vigentes de
1C y 1D. El controlador recibe temporalmente el binario porque el comando
1D exige bytes. La validación y el procesamiento del contenido permanecen
en 1D y 1C.

## Contrato HTTP

- `POST /api/v1/identity/google/session` recibe JSON con `google_id_token`. Devuelve 201 con `access_token`, `token_type`, `expires_in`, `user_id` y `role`, con `Cache-Control: no-store`.
- `POST /api/v1/content/cards` exige Bearer de plataforma y `Idempotency-Key` única de 1 a 128 caracteres ASCII visibles, sin coma. El formulario multipart contiene `name`, `cost`, `power`, `card_type`, `rarity`, `ability_code` e `image`. Los campos extra y duplicados se rechazan.
- Una creación confirmada y su replay devuelven el mismo **201** y el mismo JSON con `id`, `code`, `operation_id`, `image_id` e `image_status: "READY"`. El header `X-Correlation-ID` corresponde a la operación. El contrato no incluye URLs de lectura o proyección que 1E todavía no ofrece.
- `/docs` y `/openapi.json` documentan el Bearer, la clave, el multipart, las respuestas y ejemplos. OpenAPI declara la forma del cuerpo explícitamente porque el servidor limita el flujo antes del parseo.

```bash
curl --fail-with-body https://arena.example/api/v1/content/cards \
  -H "Authorization: Bearer ${PLATFORM_ACCESS_TOKEN}" \
  -H "Idempotency-Key: ${IDEMPOTENCY_KEY}" \
  -F 'name=Guardiana' -F 'cost=2' -F 'power=5' \
  -F 'card_type=AGU' -F 'rarity=RARA' -F 'ability_code=HAB-000' \
  -F 'image=@carta.png'
```

### Identidad y autorización

1. El intercambio verifica firma RS256 con las claves públicas de Google.
   Se exigen emisor, audiencia exacta, `exp`, `iat`, `sub` y, si existe,
   `azp` coincidente. La consulta JWKS usa una URL HTTPS fija, timeout de
   cinco segundos y caché de 300 segundos. Un `kid` desconocido se rechaza
   hasta la siguiente renovación. La verificación no bloquea el loop.
2. El servidor asocia `(GOOGLE, sub)` con el ID SQL estable. Emite 32 bytes
   aleatorios codificados como token URL-safe y persiste solamente su
   SHA-256 en una sesión con vencimiento. Un usuario obtiene
   `PLATFORM_ADMIN` mediante la lista explícita de sujetos Google.
3. Cada petición de creación consulta una sesión vigente y sin revocación
   del proveedor GOOGLE. Para crear se exigen el rol persistido
   `PLATFORM_ADMIN` y el sujeto en la lista actual. El ID SQL se transforma
   en `ActorCreacion`; los headers arbitrarios, el correo y los campos
   enviados por el usuario quedan fuera de la decisión.
4. La configuración vive en `shared/config.py`. CORS exige orígenes
   explícitos y permite los métodos y headers usados. El token se transporta
   con Authorization, sin cookies. Las sustituciones de dependencias son
   exclusivas de los tests. No hay configuración que active un proveedor TEST.

La validación aplica los criterios publicados por Google y la biblioteca
criptográfica encapsula la verificación de firmas. La expiración de la
credencial de Google es distinta de la duración de la sesión local.
[Verificación de ID tokens de Google](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
y [API de PyJWT](https://pyjwt.readthedocs.io/en/stable/api.html).

### Límites y errores

La autenticación y autorización preceden al parseo de multipart. El flujo
ASGI cuenta los bytes recibidos y corta en **5 016 384 bytes** para el cuerpo
total. El archivo tiene un límite independiente de **5 000 000 bytes**. Se
admiten seis campos de hasta 2048 bytes y un archivo. El parser verifica el
cierre del multipart y cierra temporales en error, desconexión o cancelación.
El login limita el cuerpo JSON a 16 384 bytes y el ID token a 8192 caracteres.

| HTTP | Casos |
| --- | --- |
| 401 | Credencial Bearer ausente o inválida, sesión expirada o revocada. Crear Carta incluye `WWW-Authenticate: Bearer`. El intercambio rechaza un ID token no válido. |
| 403 | Sesión válida sin permisos de plataforma. |
| 404 | Habilidad inexistente. |
| 409 | Clave en uso, huella distinta, código agotado, compensación pendiente, resultado incompatible, reserva incierta o medios que requieren conciliación. |
| 413 | Archivo o cuerpo HTTP supera el límite. |
| 415 | Content-Type HTTP incompatible con la ruta. |
| 422 | Campos, encabezados o imagen inválidos. 1C distingue el contenido válido sin confiar en el MIME enviado. |
| 503 | Identidad, almacenamiento o transacción no disponibles. Un commit incierto pide repetir con la misma clave para resolver su estado. |
| 500 | Error de procesamiento o error interno sanitizado. |

Los errores de estas operaciones usan `application/problem+json` con
`type`, `title`, `status`, `detail`, `code` y `correlation_id`. No exponen
cuerpos de entrada, tokens, trazas ni detalles de drivers. El identificador
de error se devuelve también como `X-Correlation-ID`.

## Archivos y dependencias

| Ubicación | Responsabilidad |
| --- | --- |
| `backend/src/main.py` y `modules/catalogo/catalogo_module.py` | Registro de rutas, CORS, ciclo de vida y composición del servicio existente. |
| `gestion-cartas/controllers/cartas_controller.py` y `cartas_dtos.py` | Contrato, límites multipart y traducción HTTP de Crear Carta. |
| `modules/identidad/identidad_module.py` y `gestion-sesiones/` | Composición, contrato público de administrador, dominio, puerto, servicio de sesiones y adaptadores SQL/OIDC. |
| `shared/http_module.py`, `errores-rfc7807/`, `seguridad-roles/`, `validacion/cuerpo.py`, `shared/config.py` | Composición transversal, errores, extracción de Bearer, límite de bytes y configuración. |
| `backend/pyproject.toml` | PyJWT con soporte RSA, parser multipart y Starlette con cierre de temporales ante excepciones de lectura. |
| `backend/tests/test_web_create_card.py` | Contrato ASGI, seguridad local y prueba conjunta PostgreSQL + GridFS. |
| `AGENTS.md`, `README.md` y `CARD_CREATION_BACKEND.md` | Alcance, configuración y criterios de despliegue. |

Se reutilizan FastAPI, Pydantic, HTTPX, SQLAlchemy, asyncpg, PyMongo y Pillow.
Se añadió PyJWT con soporte criptográfico. La dependencia directa de
Starlette fija el comportamiento del parser usado por el controlador.
[Cierre de temporales en Starlette](https://github.com/encode/starlette/blob/1.10.0/starlette/formparsers.py).

## Validación y comandos

Se usaron copias efímeras PostgreSQL 16 y MongoDB 7, con usuarios de
aplicación y sin volúmenes de los servicios originales. El PostgreSQL aislado
recibió la sucesora 1B.2B en la copia de aplicación. También se prepararon
dos bases vacías para reconstruir el historial y una copia en 008 para la
prueba de migración. Los permisos de identidad se otorgaron solo al rol
de la copia. Las URLs privadas se pasaron por entorno y se retiraron al
terminar.

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade 1b2b_card_image_integrity
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -p no:cacheprovider backend/tests -q -rs
backend/.venv/bin/python manage.py lint
backend/.venv/bin/python -m ruff check backend/tests/test_web_create_card.py
(cd backend && .venv/bin/python -m mypy --config-file pyproject.toml -m tests.test_web_create_card)
backend/.venv/bin/python -m compileall -q backend/src backend/tests
git diff --check
```

| Validación | Resultado |
| --- | --- |
| Suite 1A–1E con motores aislados | **194 aprobadas, 0 omitidas**. Incluye 152 regresiones. |
| Seguridad criptográfica local | 7 pruebas de verificación con RSA local, incluidas firma incorrecta, algoritmo, emisor, audiencia, expiración, sujeto y claims. |
| HTTP sin motores | 34 pruebas ASGI de contrato, OpenAPI, tamaños, autorización previa al cuerpo, CORS y traducción de errores. |
| HTTP con PostgreSQL y GridFS | 1 prueba de extremo a extremo. Intercambio firmado local, roles, sesión vencida o revocada, concurrencia, replay, conflicto, comprobación SQL, Outbox e imágenes reales. |
| Solo el archivo nuevo sin URLs aisladas | 41 aprobadas y 1 omitida por infraestructura. |
| Ruff, Mypy, compilación y diff | Aprobados. |

## Preparación de despliegue y 1F

- En un destino autorizado, configurar `GOOGLE_OAUTH_CLIENT_ID` para el
  cliente web registrado, `PLATFORM_ADMIN_GOOGLE_SUBJECTS` con los sujetos
  autorizados, `IDENTITY_ACCESS_TOKEN_TTL_SECONDS` y `ALLOWED_ORIGINS`. Usar
  HTTPS y no registrar cuerpos ni encabezados de autenticación. Confirmar
  el flujo con un ID token real emitido para ese cliente y las claves de Google.
- Los guards de 1D y de emisión de sesiones siguen limitados a bases de
  validación `pokearena_alembic_*`. Para habilitar el original hacen falta
  autorización de destino, la migración 1B.2B, los permisos GridFS y de
  lectura de `alembic_version`, además de SELECT en las dos tablas de
  identidad, INSERT de usuarios y sesiones y UPDATE de `role` y
  `updated_at` de usuarios. El original no recibió esas modificaciones.
- La prueba de integración usó HTTP por ASGI en el mismo proceso. TLS,
  configuración del proxy y obtención del token Google real quedan para
  el ensayo de despliegue. Configurar plazos de lectura y límites de
  concurrencia del proxy de acuerdo con el límite de cuerpo de 1E.
- El consumidor de `CardCreated`, la publicación y la proyección se
  mantienen pendientes de 1F. La respuesta 201 certifica la creación SQL
  y ambas imágenes verificadas, sin certificar publicación en MongoDB.
