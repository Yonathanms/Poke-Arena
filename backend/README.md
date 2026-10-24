# Poké-Arena Backend

Módulo backend para Poké-Arena construido con **FastAPI** y arquitectura **Monolito Modular Hexagonal**.

## Requisitos
* Python 3.12+
* Docker & Docker Compose (para bases de datos PostgreSQL y MongoDB)

## Estructura
* `src/shared/`: Kernel compartido (excepciones RFC 7807, middleware de correlación, conexiones SQL/NoSQL).
* `src/modules/content/`: Módulo de Cartas y Ubicaciones (Sprint 1).
* `alembic/`: Migraciones versionadas de PostgreSQL.
* `tests/`: Suites de pruebas unitarias, de integración y arquitectura.

## Identity para Crear Carta

El backend intercambia un ID token de Google por un bearer opaco de Poké-Arena en
`POST /api/v1/identity/google/session`. Configure `GOOGLE_OAUTH_CLIENT_ID` con el
Client ID web de Google y `PLATFORM_ADMIN_GOOGLE_SUBJECTS` con una lista separada
por comas de los `sub` autorizados como administradores. Los correos no asignan
permisos. `IDENTITY_ACCESS_TOKEN_TTL_SECONDS` controla la vigencia (60–86400 s).

Las credenciales de Google y la lista de administradores se configuran por entorno;
no deben agregarse al repositorio. Sin Client ID, el login queda cerrado y responde
503. El frontend debe enviar el `access_token` recibido como `Authorization: Bearer`.

Para desarrollo sin conexión, Compose inicia por defecto con
`POKEA_ENVIRONMENT=development`. El frontend mostrará **Entrar como admin local** y
usará `POST /api/v1/identity/test-session`; este endpoint solo se registra en los
entornos `development` y `test`, y emite un rol administrativo fijo del proveedor
`TEST`. No acepta permisos del cliente. En producción, configure explícitamente
`POKEA_ENVIRONMENT=production`; el endpoint local no estará registrado.

Crear Carta acepta imagen JPG/JPEG, PNG o WebP opcional, de hasta 5 MB, con
resolución mínima 300 × 420 y proporción 5:7 con tolerancia del 5%. La miniatura
se recorta al centro a 200 × 280; el original se conserva. Sin imagen, la ficha se
guarda como borrador no disponible para partidas. Las imágenes se procesan con el
worker durable.

Antes de iniciar API o workers, aplique la migración desde `backend/` con
`alembic upgrade head`. FastAPI no crea ni migra tablas durante el arranque.
