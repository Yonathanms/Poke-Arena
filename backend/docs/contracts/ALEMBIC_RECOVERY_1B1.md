# Entrega 1B.1 — Recuperación y validación de Alembic

Fecha: 2026-11-06. Alcance autorizado: recuperar originales hasta 008 y reconstruir exclusivamente bases aisladas. No se autoriza 1B.2, sucesoras ni ejecución sobre bases existentes.

## Resultado

Se recuperaron sin modificaciones ocho archivos del commit `8a9e309fefd0cbd291b6d371180ddce4ed74338d`. Las dos reconstrucciones iniciales terminaron en `008_flex_card_img_dims`, desde raíz y desde `backend/`, con rol `pokearena_migrator` no administrativo y sin URLs válidas de aplicación/MongoDB en esos procesos. La instancia activa permaneció sin cambios.

| Revisión | Padre | Último cambio del archivo recuperado |
|---|---|---|
| `001_initial_schema` | base | `76dd130` |
| `002_content_card_persistence` | `001_initial_schema` | `9e37ad5` |
| `003_creation_idempotency_outbox` | `002_content_card_persistence` | `9e37ad5` |
| `004_processing_recovery` | `003_creation_idempotency_outbox` | `9e37ad5` |
| `005_identity_sessions` | `004_processing_recovery` | `8a9e309` |
| `006_identity_local_test_provider` | `005_identity_sessions` | `8a9e309` |
| `007_cards_without_image` | `006_identity_local_test_provider` | `8a9e309` |
| `008_flex_card_img_dims` | `007_cards_without_image` | `8a9e309` |

Procedencia verificable: `backend/alembic/history_manifest.json` registra commit fuente, commit de introducción/último cambio, Git blob y SHA-256 por archivo. El commit `4843809f67c993a8682f60ad894863843133bbb8` eliminó estas revisiones del árbol; no del historial. Las pruebas comprueban identidad de bytes, cadena única y ausencia de duplicados.

`009_location_extended_fields`, incorporada en `02a2b89`, queda fuera de `versions/`. Se verificó que sus columnas de ubicaciones no existen en la base activa ni en las reconstrucciones. No se modificó ninguna revisión histórica, incluidos sus cuerpos `downgrade`; no se ejecutó downgrade, stamp ni una inicial alternativa. Se preserva literalmente el código histórico aunque sus docstrings/formato no cumplan las convenciones actuales.

## Dependencias y configuración

Los ocho originales solo importan biblioteca estándar, SQLAlchemy y Alembic. No requieren restaurar el módulo eliminado `content`, ORM ni funcionalidades de identidad. 002 sí inspecciona tablas y consulta datos del legado: necesita conexión real; generar toda la cadena con `--sql` no es un escenario soportado. Se rechaza explícitamente para evitar presentar SQL incompleto como reproducción válida.

- `MigrationSettings`, en la configuración central existente, comparte ubicación de `.env` y timeout con el runtime sin exigir `DATABASE_URL` o `MONGO_URL`.
- `MIGRATION_DATABASE_URL` es obligatoria para comandos que conectan; sin fallback a la API. No se guarda en `alembic.ini` ni contiene defaults con contraseñas en código. La plantilla la deja vacía; las credenciales aisladas se mantienen en archivo privado ignorado y se pasan por entorno.
- Durante 1B.1 se aceptan solo bases `pokearena_alembic_*`; se rechazan `pokearena_db`, las demás bases originales y `poke_api_user` antes de conectar. Dentro de la transacción se comprueban base, rol real y atributos: sin superusuario, CREATEDB, CREATEROLE, REPLICATION o BYPASSRLS. No se concedieron permisos adicionales al usuario de API ni se alteró el rol migrador original.
- `env.py` usa el engine de mantenimiento estándar async de Alembic/SQLAlchemy con NullPool, timeout y cierre en `finally`. No importa el engine de aplicación ni clientes Mongo. La transacción valida identidad antes del DDL. La URL se pasa directamente al engine para evitar interpolación de `%` en ConfigParser.
- `script_location` y `prepend_sys_path` utilizan `%(here)s`, relativo al INI. `path_separator=os` conserva rutas con espacios. Esta opción existe desde Alembic 1.16: se ajustó el mínimo de la dependencia ya existente a `>=1.16.0`; se probó con 1.20.1, sin instalar bibliotecas nuevas.
- No hay metadata ORM completa y `autogenerate` queda bloqueado. La reproducción usa los scripts originales, no metadata vacía como sustituto del esquema. No fue necesario importar directorios con guiones, modificar `sys.path` manualmente ni renombrar carpetas; esa decisión sigue pendiente antes de incorporar modelos.

Referencias primarias: [configuración y path_separator de Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html#editing-the-ini-file), [patrón async oficial](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic).

## Aislamiento y comparación

Se creó `pokearena-1b1-alembic-20261106`, con la misma imagen local PostgreSQL 16 que el primario, red propia, puerto publicado exclusivamente en loopback y volumen nuevo `pokearena_1b1_alembic_20261106`. Ningún volumen o red de las fuentes se montó en esa instancia. Se conservan instancia detenida, volumen y red de validación; no se eliminó ningún volumen.

Durante el desarrollo se conservaron tres pares de bases independientes (seis reconstrucciones); la suite final se ejecutó sobre el último par nuevo y aprobó 24 pruebas. Cada reconstrucción parte de una base nueva sin tablas, propiedad del rol aislado `pokearena_migrator`, distinto del bootstrap administrativo. La prueba rechaza una base no vacía en lugar de limpiarla. Los comandos Alembic nunca apuntaron al servidor original. No se modificó Docker Compose ni se reiniciaron PostgreSQL/MongoDB originales.

| Elemento inspeccionado | Reconstrucción | Base activa | Diferencia estructural |
|---|---:|---:|---|
| Tablas | 12 | 12 | Ninguna |
| Columnas, tipos, nulabilidad, defaults e identity | 103 | 103 | Ninguna |
| PK, FK, UNIQUE y CHECK | 50 | 50 | Ninguna |
| Índices y definiciones | 27 | 27 | Ninguna |
| Funciones | 1 | 1 | Ninguna |
| Triggers no internos | 1 | 1 | Ninguna |
| `alembic_version` | 008 | 008 | Ninguna |

La comparación normaliza exclusivamente dos formas equivalentes de deparsear casts en arrays de literales de texto. No normaliza nombres, tipos de columnas, rangos ni claves. Excluye propietarios y ACL: el rol aislado es propietario de su base y la fuente conserva los permisos técnicos de 1A. No se igualaron propietarios/permisos mediante modificaciones a las fuentes.

Se verificaron también PK `VARCHAR(36)` de entidades, cuatro FKs, contador con PK natural, código inmutable, seeds de `HAB-000` y seis contadores iniciales en cero. Los datos de una base vacía no deben igualarse a los de desarrollo: por ejemplo, el contador PLA confirmado de la fuente se conserva y no se reinicia. 007 mantiene imagen nullable y 008 conserva las dimensiones flexibles históricas; la discrepancia con el requisito funcional estricto de imagen sigue pendiente para una fase posterior autorizada, sin corrección automática.

La API no puede leer `alembic_version`, conforme a sus privilegios mínimos. La revisión activa se consultó por lectura administrativa separada; no se amplió ese acceso. Las huellas de filas y esquema de las cuatro bases SQL, IDs/tiempos de inicio/montajes de los contenedores originales permanecieron iguales antes y después. Los dos servicios originales siguen saludables.

## Comandos y pruebas

Desde raíz, sin conectar a motores:

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini history
backend/.venv/bin/python -m alembic -c backend/alembic.ini heads
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/test_infrastructure_config.py backend/tests/test_alembic_recovery.py -q
```

Con `MIGRATION_DATABASE_URL` configurada privadamente para una base aislada vacía:

```bash
# Desde raíz:
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade 008_flex_card_img_dims
# Desde backend, sobre OTRA base aislada vacía:
.venv/bin/python -m alembic -c alembic.ini upgrade 008_flex_card_img_dims
```

La prueba de integración opt-in lee `ALEMBIC_TEST_URL_A/B` desde el entorno, comprueba que las bases están vacías, ejecuta esos comandos con URLs de aplicación/Mongo inválidas y compara todos los objetos. Las URLs deben provenir de una instancia aislada nueva, no del servidor de desarrollo. Sin ambas URLs, esa única prueba se omite de forma explícita; las pruebas de hashes/configuración no necesitan Docker.

Resultado final: **24 pruebas aprobadas, sin omisiones en la ejecución con las dos URLs aisladas**. En ejecución local sin URLs: 23 aprobadas y una integración omitida explícitamente.

Resultados y huellas de esta ejecución: `docker-data/validation/1b1-20261106/`, privado e ignorado. Conserva `.env` de validación (secreto), snapshots sin datos de negocio, comparación, log sanitizado y scripts operativos. Los scripts son evidencia de la ejecución, no una CLI pública estable. No reejecutar la provisión sobre nombres existentes ni borrar bases para repetir: crear destinos aislados nuevos.

Incidencias de validación corregidas sin tocar fuentes: separación legacy de paths con espacios, representación NUL del char interno vacío en asyncpg y reasignación de puerto aleatorio Docker tras iniciar la instancia aislada (se relee antes de conectar). No se modificaron migraciones históricas para resolverlas.

No se ejecutaron Ruff/Mypy porque no están instalados. Se comprobaron compilación Python, longitud de líneas del código nuevo, hashes originales y `git diff --check`. No se realizó commit ni push.

## Recomendaciones y límite de etapa

1. Conservar esta cadena sin reescrituras y usar 008 explícitamente como referencia reproducible.
2. Antes de 1B.2, acordar únicamente los ajustes realmente necesarios, la estrategia de modelos/imports y la política de aplicación a desarrollo. El guard de aislamiento no debe retirarse sin esa autorización.
3. No aplicar 009 por estar disponible en Git; su alcance de ubicaciones se evalúa separadamente.
4. No ejecutar autogenerate con metadata incompleta, ni usar stamp para ocultar divergencias.

**No se modificaron las bases, roles, contenedores ni volúmenes originales. No se avanzó a 1B.2.**
