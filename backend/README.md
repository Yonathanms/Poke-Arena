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
