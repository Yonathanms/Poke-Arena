# AGENTS.md — Poké-Arena

**Actualización documental:** 2026-11-06. Contrato complementario v1.3.
**Fase autorizada actualmente:** Entrega 1A — Infraestructura Docker, por instrucción explícita posterior a la fase documental. Se permiten configuración, conexiones oficiales, pruebas de infraestructura, respaldos/restauración aislada y documentación. No cambiar tablas, modelos, migraciones, estructura de carpetas, endpoints ni lógica de negocio. La autorización posterior permite retirar únicamente los dos binds obsoletos de initdb.d, recrear los servicios conservando imágenes/volúmenes/red/puertos y configurar poke_api_user/poke_api_mongo. Esto revoca la decisión previa de conservar credenciales inválidas. 1A completada y verificada; detenerse antes de fase 0/1B y ante cualquier cambio adicional de datos o topología.

## 1. Autoridad y alcance

Este archivo es la guía de trabajo obligatoria para Codex en el repositorio **Poke-Arena**. Antes de ejecutar una tarea, inspecciona el árbol real: el usuario proporcionó la **estructura oficial**, pero no se garantiza que los archivos contengan una implementación completa. **No inventes código existente ni sustituyas su contenido sin leerlo.**

**Orden de autoridad técnica para este trabajo** (si hay contradicciones, informar, no asumir silenciosamente):
1. Instrucción actual y fase autorizada por el usuario.
2. `ESTRUCTURA-REPOSITORIO.md` y la estructura oficial ya existente.
3. Notas de diseño aplicables: `backend/src/modules/nota-diseño.txt`, `backend/src/database/explicacion_database.txt`, `backend/src/shared/NOTA-IMPORTANTE.md`, `backend/alembic/NOTA-IMPORTANTE.txt`, otras notas existentes.
4. `backend/docs/contracts/CARD_CREATION_BACKEND.md` (contrato técnico v1.3, actualizado tras la auditoría).
5. Código, pruebas, dependencias y convenciones reales del repositorio.

Las decisiones aprobadas por el usuario y registradas en §5 y en el contrato §1.2 prevalecen sobre descripciones anteriores incompatibles, sin autorizar cambios fuera de la fase vigente. Se conserva el árbol modular oficial. Las contradicciones restantes (incluida la descripción ORM del dominio en las notas antiguas) deben registrarse y resolverse antes de implementar; no se reestructura código por esa discrepancia en 1A.

Si hay discrepancias materiales con decisiones anteriores, documentarlas y consultar **antes de reestructurar carpetas o romper contratos**. No suponer que el diseño en papel prevalece sobre código funcionando sin evaluar impacto.

## 2. Estructura oficial: usar, no duplicar

- `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`, `manage.py` y `ESTRUCTURA-REPOSITORIO.md` están en la **raíz**, no en `backend/`.
- Backend en `backend/src/`. Entry point `backend/src/main.py`. Configuración central: `backend/src/shared/config.py`.
- PostgreSQL: `backend/src/database/postgresql/connection.py`. MongoDB: `backend/src/database/mongodb/connection.py`. No crear conexiones alternativas en otras carpetas.
- Alembic: `backend/alembic.ini`, `backend/alembic/env.py` y `backend/alembic/versions/`.
- **User Story 2.1.1 Crear carta:** `backend/src/modules/catalogo/gestion-cartas/`, con `adapters/`, `controllers/`, `domain/`, `ports/`, `services/`.
- Controlador/DTO: `controllers/cartas_controller.py`, `controllers/cartas_dtos.py`.
- Dominio: `domain/carta_model.py`. Puertos: `ports/cartas_ports.py`. Caso de uso: `services/cartas_service.py`.
- Adaptadores: `adapters/sql_carta_repository.py`, `adapters/mongo_carta_repository.py`, `adapters/imagen_carta_adapter.py`.
- Composición del catálogo: `backend/src/modules/catalogo/catalogo_module.py` (fase de API; no duplicar su función en `main.py`).
- Componentes comunes: `backend/src/shared/idempotencia/`, `validacion/`, `seguridad-roles/`, `errores-rfc7807/` y `observabilidad/`.
- Pruebas: `backend/tests/` (incluido `concurrency/`). Frontend oficial: `frontend/src/web-admin/modules/catalogo/`, **fuera del alcance actual**.
- `backend/src/database/outbox_worker.py` ya figura en la estructura: **no modificar ni duplicar** un worker sin leer las decisiones de arquitectura existentes.

**Prohibido** crear por inercia `backend/app/`, `backend/app/features/`, `backend/app/db/`, `backend/infra/`, `backend/scripts/`, `backend/compose.yaml`, `backend/README.md` o un nuevo `compose.yaml` en raíz. Reutilizar rutas oficiales. Se permiten archivos nuevos **dentro de carpetas oficiales** solo si su responsabilidad está justificada y no duplica un archivo existente.

**Aviso importante — guiones en nombres de carpetas:** directorios oficiales como `gestion-cartas`, `gestion-ubicaciones`, `motor-juego` y `errores-rfc7807` no pueden utilizarse directamente con sintaxis convencional `from ... import ...` de Python. No emitir imports inválidos, no insertar hacks de `sys.path` ni renombrar rutas oficiales sin aprobación. **Antes de la fase que requiera importar esos módulos**, proponer una decisión mínima y documentada (preferir `snake_case` si el equipo permite renombrar; de lo contrario, justificar estrategia alternativa compatible con la estructura oficial). La fase Docker 1A no debe bloquearse por esto.

## 3. Arquitectura hexagonal y dependencias

- `controllers`: adaptación HTTP, autenticación/autorización y DTOs. Sin SQL ni bytes de imagen.
- `services`: casos de uso, orquestación, invariantes, idempotencia y coordinación a través de puertos. Sin dependencias de FastAPI ni consultas SQL directas.
- `domain`: entidades, tipos y reglas puras; **nunca** importar SQLAlchemy, PyMongo, GridFS, FastAPI o infraestructura.
- `ports`: contratos/Protocol de interfaces que necesitan los servicios; no implementaciones.
- `adapters`: código de infraestructura que implementa puertos: SQL, Mongo/Medios y procesamiento de imagen. No construir respuestas HTTP.
- `database`: conexión y ciclo de vida de clientes/sesiones compartidos; no lógica del catálogo.
- `shared`: únicamente infraestructura/reglas transversales; la validación específica de carta permanece en catálogo.
- Dirección de dependencias: `controllers -> services -> ports/domain`; `adapters -> ports/domain`; composición/inyección fuera del dominio. Un módulo no accede a implementaciones internas de otro.
- La entidad SQL `catalog_abilities` existe para dar soporte a la FK y `HAB-000`, pero **el árbol oficial no incluye aún un módulo `gestion-habilidades`**. No inventarlo ni implementar Crear habilidad dentro de Crear carta; permitir lectura de habilidades existentes mediante un puerto.
- El modelo `domain/carta_model.py` **no es** modelo ORM. Si se necesitan mapeos SQLAlchemy, ubicarlos dentro del adaptador SQL o en un archivo adicional de `adapters/` justificado y autorizado.

## 4. Regla innegociable: Clean Code + documentación con cada cambio

El trabajo **no termina** cuando el código compila: cada cambio debe ser legible, verificable, documentado y mantener los límites anteriores.

1. **Responsabilidad única:** cada función/clase tiene un propósito cohesionado. Una función orquestadora puede coordinar varios pasos, pero no mezclar HTTP, consultas SQL, procesado de imágenes y reglas de dominio en un bloque multipropósito. Extraer helpers cuando agreguen claridad, no wrappers vacíos.
2. **DRY y simplicidad:** reutilizar componentes reales, eliminar duplicación y evitar sobreingeniería. Antes de crear un archivo, buscar si su responsabilidad ya existe en la estructura oficial.
3. **Nombres:** respetar los nombres oficiales existentes en español (`cartas_*`, `carta_model`, etc.); nombres nuevos claros y consistentes, convenciones Python (`snake_case`, `PascalCase`, tipos), sin traducciones automáticas por gusto. Tablas/columnas SQL según contrato en inglés.
4. **Docstring por módulo Python nuevo** explicando propósito y límites; cada clase/función pública nueva o modificada de servicios, repositorios, adaptadores, infraestructura y scripts debe documentar contrato, entradas/salidas relevantes, errores, efectos secundarios e invariantes no obvias. Funciones privadas complejas también. Tipos anotados.
5. **Comentarios útiles, no redundantes:** explicar decisiones de concurrencia, seguridad, consistencia y porqués no evidentes; no narrar línea por línea ni repetir firmas. Evitar código muerto y comentarios de relleno.
6. **Pruebas junto con código:** agregar o actualizar pruebas válidas, inválidas y límites. Para SQL incluir restricciones, concurrencia e idempotencia cuando la fase lo requiera. No afirmar resultados que no se ejecutaron.
7. **Documentación viva:** actualizar `README.md` en raíz si cambia la forma de instalar, ejecutar o probar; actualizar este contrato si cambian estructuras/esquemas/reglas; registrar decisiones significativas en ADR en ubicación acordada (no inventar sin necesidad). Migraciones Alembic y configuraciones complejas llevan explicación pertinente.
8. **Seguridad:** sin credenciales hardcodeadas; usar `.env` no versionado, `.env.example` sin valores reales, logs sin secretos ni binarios, clientes con privilegios mínimos. No introducir nuevas bibliotecas sin comprobar `backend/pyproject.toml`.
9. **Separación dominio/infraestructura:** no confundir modelos de dominio con SQLAlchemy, DTOs HTTP o documentos de Mongo. Dependencias inyectadas por puertos.
10. **Checklist de salida:** revisar SRP, DRY, nombres, docstrings, tipos, pruebas, README/ADR, límites hexagonales y archivos modificados. Indicar cualquier excepción de manera explícita.

## 5. Decisiones de datos aprobadas tras la auditoría

Estas decisiones sustituyen las propuestas incompatibles de v1.2; son acuerdos de diseño, no evidencia de implementación completada.

1. **Reutilizar tablas y nombres físicos:** `catalog_cards`, `catalog_abilities`, `catalog_card_code_counters`, `shared_idempotency_records`, `catalog_card_images` y `shared_outbox`. No crear tablas paralelas `cards`, `abilities`, `card_code_counters` ni `idempotency_requests`.
2. **Conservar PK actuales:** identificadores de entidades `VARCHAR(36)` y sus FKs; sin conversión a BIGINT ni identity. El contador mantiene su PK natural `card_type`.
3. **Tipos canónicos:** `FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC`, usando `card_type`. Rarezas: `COMUN`, `POCO_COMUN`, `RARA`, `LEGENDARIA`.
4. **Fuente de verdad de imágenes:** `catalog_card_images` controla metadatos, referencias y estado. La relación existente es `catalog_cards.image_id -> catalog_card_images.id`. No añadir un segundo estado autoritativo en cartas o MongoDB.
5. **Binarios:** original y miniatura se almacenarán en MongoDB GridFS sobre volúmenes locales persistentes. No crear una colección propia redundante de metadatos `card_images`; las colecciones internas del bucket son necesarias y no equivalen a esa duplicación. El formato de referencia SQL/GridFS y el nombre definitivo del bucket quedan pendientes.
6. **Conservar proyección y Outbox:** preservar `pokearena_catalog.cards_projection`, sus índices, `shared_outbox` y el archivo oficial `outbox_worker.py`. No activar nuevos procesos, modificar el worker ni crear otro worker en esta fase.
7. **Versiones:** mantener PostgreSQL 16 (`postgres:16-alpine`) y MongoDB 7 (`mongo:7.0`), sin actualización mayor por esta alineación.
8. **Alembic antes de sucesoras:** recuperar y verificar el historial existente en una fase autorizada antes de proponer migraciones sucesoras. La base auditada registra `008_flex_card_img_dims`; el historial está en Git aunque falte en el árbol actual. No ejecutar autogenerate con metadata incompleta, `stamp` para ocultar diferencias, `create_all()` ni DDL paralelo.
9. **Conservación:** no reiniciar contadores, reemplazar seeds válidos ni borrar datos históricos. Preservar las otras tablas y referencias. Código público único e inmutable `PKA-<TIPO>-<NNN>`; costo 0–10, poder -20–20 y habilidad obligatoria válida.
10. **Ingeniería:** conservar arquitectura modular oficial, Clean Code, SOLID, DRY, tipos, pruebas pertinentes y documentación obligatoria.

**Requisitos funcionales que continúan vigentes:** original PNG/JPEG/WebP, máximo 5 000 000 bytes, proporción exacta 5:7, mínimo 600x840 y miniatura 200x280. Disponibilidad solo con estado `READY` en `catalog_card_images` y verificación real de ambos archivos. La revisión 008 admite imágenes más pequeñas y proporción flexible: es una discrepancia pendiente de resolver mediante una futura propuesta, no permiso para alterar datos ahora. Imagen inicialmente inválida no crea carta. Reintentos no duplican carta ni consumen otro código. SQL y GridFS no comparten transacción distribuida.

**Pendientes:** estrategia síncrona/asíncrona, reintentos y reconciliación; serialización de referencias GridFS en SQL; bucket/base de medios y transición desde archivos locales; recuperación/retención idempotente; evolución de habilidades y conservación histórica; política de activación/desactivación; importaciones con guiones y discrepancia documental ORM. No resolverlos por inferencia ni crear columnas/colecciones para anticiparlos. Véase contrato §9.

## 6. Fases: ejecutar SOLO la autorizada

- **D — Documentación (completada):** actualizar `AGENTS.md` y `backend/docs/contracts/CARD_CREATION_BACKEND.md`. Ninguna operación de implementación.
- **0 — Recuperación/verificación histórica (pendiente de autorización):** recuperar las revisiones desde Git y verificar cadena, metadata y correspondencia con 008 en bases aisladas. Evaluar 009 de ubicaciones por separado; no aplicarla automáticamente. No proponer sucesoras hasta completar esta verificación.
- **1A — Infraestructura (completada):** Compose aplicado con recursos externos reales, motores 16/7, puertos loopback y healthchecks autenticados. Usuarios técnicos verificados; ambos contenedores recreados con mismas imágenes/volúmenes/red/puertos, retirando solo binds obsoletos autorizados. Datos y estructura conservados; ACL/cuentas cambiadas explícitamente. Evidencia y privilegios detallados en README; no repetir recreación o rotación por inercia.
- **1B — Compatibilidad SQL (pendiente):** tras fase 0, proponer y revisar ajustes mínimos sobre las tablas existentes. Aplicar sucesoras solo con autorización específica y pruebas aisladas. Conservar IDs, códigos, contadores, seeds y fuentes de verdad; no hacer una migración inicial paralela.
- **1C — GridFS (pendiente):** preparar almacenamiento de binarios y referencias desde SQL según decisiones pendientes aprobadas, sin colección redundante de metadatos ni activación de procesos nuevos. Reutilizar conexión y adaptador oficiales.
- **2 — Caso de uso/API (pendiente):** implementar servicio, puertos, adaptadores, validación, idempotencia, autorización y consistencia conforme a decisiones explícitas. No incluye permiso implícito para activar workers.
- **3 — Frontend/integración (pendiente):** integrar el frontend oficial solo con autorización separada.

La autorización explícita de 1A no autoriza ejecutar fase 0 ni migraciones: verificar el historial sigue siendo condición previa a proponer sucesoras. En el cierre autorizado de 1A se retiraron los dos binds ausentes y se conservaron red y volúmenes. El primario mantiene identidad/configuración y no tenía réplicas activas ni slots; no tocar el volumen de réplica histórica. SQL usa permisos por tabla sin administración y Mongo rol local solo sobre cards_projection; ampliar permisos GridFS requiere decisión explícita del bucket y autorización. Véase estado y evidencia en README de raíz.

No alterar `gestion-ubicaciones`, `identidad`, `motor-juego`, `torneos` ni `frontend` durante las fases 0–1C salvo alcance adicional explícito. Cada fase tiene criterios detallados en el contrato §7; terminar una no autoriza la siguiente.

## 7. Procedimiento de trabajo y entrega

1. Leer este archivo, contrato y notas oficiales. Inspeccionar el árbol y **leer antes de editar** cada archivo existente.
2. Presentar alcance y nombres de archivos a modificar; identificar contradicciones con el repositorio en vez de sobrescribirlas.
3. Hacer cambios mínimos en la fase autorizada, con documentación Clean Code y tests de la misma fase.
4. Ejecutar solo validaciones seguras: `docker compose -f docker-compose.yml config`, healthchecks, pruebas; recuperación/verificación Alembic únicamente en fase 0 autorizada y bases aisladas; aplicar sucesoras solo en 1B autorizada y contra base aprobada. En fase D limitarse a comprobaciones documentales locales. No inventar resultados.
5. Reportar **archivos creados/modificados, decisiones, comandos exactos, pruebas ejecutadas con su resultado, pendientes y riesgos**.
6. No ejecutar acciones destructivas (`docker compose down -v`, limpieza de volúmenes, migrations downgrade sobre datos reales, borrados masivos) sin permiso explícito.
7. **Detenerse** al acabar la etapa; no avanzar a la siguiente sin indicación.

**Contrato complementario obligatorio:** `backend/docs/contracts/CARD_CREATION_BACKEND.md`.
