# Poké-Arena — Contrato técnico del backend: Catálogo de Cartas / Crear carta

**Versión:** 1.3 — alineación documental con auditoría y decisiones aprobadas

**Fecha:** 2026-11-06

**Estado:** 1A, 1B.1 y 1B.2A cerradas. 1B.2B y 1C validadas en aislamiento. La base original permanece en 008.

**Historia de usuario:** 2.1.1 — Crear carta

**Feature:** 2.1 — Catálogo de Cartas

> **Alcance vigente: Entrega 1G en aislamiento.** La creación HTTP, el administrador local y el worker están integrados. Google real, los servicios originales y el frontend requieren autorización independiente.

**Base de información:** auditoría del repositorio, historial Git, esquema PostgreSQL y metadatos Docker/MongoDB. Los hechos de auditoría son una instantánea que debe revalidarse antes de implementar; no representan pruebas de aceptación del sistema completo. Esta versión sustituye las propuestas incompatibles de v1.2: tablas paralelas, IDs BIGINT, tipos largos y colección propia de metadatos MongoDB.

**Autoridad:** las decisiones explícitas del usuario recogidas en §1.2 prevalecen sobre descripciones anteriores incompatibles. Se conserva la topología modular de `ESTRUCTURA-REPOSITORIO.md`; las discrepancias documentales restantes se señalan en §9. La fase D ya terminó; en 1A se actualiza documentación de infraestructura sin reestructurar módulos.

---

## 1. Alcance y decisiones acordadas

### 1.1 Requisitos provenientes del enunciado

- Una carta tiene nombre, costo entre **0 y 10**, poder entre **-20 y 20**, tipo, rareza, una habilidad obligatoria e imagen.
- Tipos: **Fuego, Agua, Planta, Eléctrico, Psíquico, Lucha**.
- Rarezas: **Común, Poco común, Rara, Legendaria**.
- Código único e inmutable `PKA-<TIPO>-<NNN>`; abreviaturas `FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC`; consecutivo independiente por tipo de tres cifras, comenzando en `001`.
- La habilidad se selecciona **por su código** entre habilidades existentes. Debe existir `HAB-000` (**Sin Habilidad**) desde el inicio. Las habilidades son reutilizables.
- El administrador sube **una** imagen PNG, JPEG o WebP de máximo **5 MB**, proporción vertical **5:7** y resolución mínima **600 × 840**. El servidor genera una miniatura **200 × 280**.
- La carta **no es visible para los jugadores** hasta contar con ambas imágenes. El administrador puede consultar el estado del procesamiento; el sistema reintenta ante fallos.
- Datos inválidos, imagen inválida y habilidad inexistente se rechazan. No se guarda una carta ante una imagen inicialmente inválida.
- Crear dos cartas simultáneamente del mismo tipo no debe producir el mismo código.
- Reintentar la **misma solicitud** no debe duplicar cartas ni reservar otro código.
- Las evoluciones que se asignen a cartas no pueden apuntar a la propia carta ni formar ciclos.
- Solo los administradores autorizados podrán crear cartas. Un usuario no autenticado y uno sin permisos deben recibir errores diferentes.

**Otros requisitos relacionados:** RNF-ALM-01/02/03 (SQL + NoSQL, consistencia y conservación de contenido), RNF-ARQ-03/05 (fronteras de módulos y SOLID), RNF-API-01/03 (contrato OpenAPI y errores), y RNF-PRU-01 (pruebas). La API no forma parte de la primera entrega.

### 1.2 Decisiones aprobadas tras la auditoría

| N.º | Decisión aprobada | Consecuencia contractual |
|---|---|---|
| 1 | Reutilizar tablas SQL y nombres físicos existentes | `catalog_cards`, `catalog_abilities`, `catalog_card_code_counters`, `shared_idempotency_records`, `catalog_card_images` y `shared_outbox`; sin tablas paralelas. |
| 2 | Conservar PK actuales `VARCHAR(36)` | Mantener identificadores y FKs; no migrar a BIGINT ni identity. El contador conserva PK natural `card_type`. |
| 3 | Mantener tipos abreviados | `FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC` en `card_type`; textos localizados en presentación. |
| 4 | SQL como autoridad de imágenes | `catalog_card_images` conserva metadatos, referencias y estado; relación existente mediante `catalog_cards.image_id`. |
| 5 | GridFS para almacenamiento físico | Original y miniatura en MongoDB sobre volúmenes locales persistentes, sin servicios cloud. |
| 6 | Evitar metadatos redundantes | No crear una colección propia `card_images`; los archivos y colecciones internas de GridFS no sustituyen el registro autoritativo SQL. |
| 7 | Conservar proyección y Outbox | Preservar `pokearena_catalog.cards_projection`, sus índices, `shared_outbox` y `outbox_worker.py`; no activar nuevos procesos todavía. |
| 8 | Mantener motores actuales | PostgreSQL 16 y MongoDB 7; sin salto de versión mayor por esta alineación. |
| 9 | Recuperar/verificar Alembic primero | Verificar el historial existente antes de proponer sucesoras; no crear una migración inicial alternativa. |
| 10 | Mantener disciplina de ingeniería | Arquitectura modular oficial, Clean Code, SOLID, DRY, pruebas pertinentes y documentación obligatoria. |

**Reglas conservadas:** PostgreSQL es fuente de verdad de entidades, relaciones y códigos. Backend inicialmente en el host; conexiones oficiales únicas, I/O coherente con la implementación asíncrona y dependencias de `backend/pyproject.toml`. No reemplazar librerías por copiar ejemplos. No hay FK obligatoria de carta a administrador; la API futura deberá autenticar y autorizar. Las modificaciones de esquema requieren Alembic y autorización.

**No aprobado aún:** procesamiento síncrono/asíncrono, política de reintentos/reconciliación, contrato exacto de referencias GridFS, bucket/base de medios, ampliaciones SQL y activación de workers. La propuesta síncrona de v1.2 no se considera una elección vigente. Véase §9.

> GridFS no es obligatorio técnicamente por el límite de 5 MB: es la decisión de almacenamiento aprobada. No ofrece una transacción común con PostgreSQL.

---

## 2. Reglas obligatorias de ingeniería

### 2.1 Modularidad, arquitectura hexagonal y responsabilidades

- **La estructura oficial del repositorio es autoritativa.** Revisar `ESTRUCTURA-REPOSITORIO.md`, `backend/src/modules/nota-diseño.txt`, `backend/src/shared/NOTA-IMPORTANTE.md`, `backend/alembic/NOTA-IMPORTANTE.txt` y las notas de `backend/src/database/` cuando existan. No inferir que los archivos listados están implementados ni sobrescribirlos sin leerlos.
- Organización **por módulo de negocio** y capas hexagonales: `controllers` (HTTP/DTO), `services` (caso de uso), `domain` (modelo/reglas), `ports` (contratos de dependencia) y `adapters` (persistencia/procesamiento externo).
- **Regla de dependencias:** `controllers → services → ports/domain` y `adapters → ports/domain`. `domain` nunca importa FastAPI, SQLAlchemy, PyMongo, Docker ni frameworks HTTP. Servicios usan puertos; adaptadores implementan puertos. Las conexiones se obtienen de `backend/src/database` mediante configuración compartida.
- **Una función, una responsabilidad cohesionada.** Se admite que un caso de uso orqueste pasos, pero se prohíbe mezclar en la misma función consultas SQL, detalles de GridFS, decodificación/transformación de imágenes y generación de respuestas HTTP.
- **DRY:** no duplicar lógica de negocio, utilidades, constantes ni acceso a bases. No abstraer por anticipación: una interfaz se justifica en una frontera real (repositorio SQL, repositorio Mongo, adaptador de imágenes).
- En `cartas_controller.py` solo transporte HTTP, dependencias y autorización cuando esa fase sea autorizada; contratos de entrada/salida en `cartas_dtos.py`.
- En `cartas_service.py` únicamente coordinación del caso de uso y sus invariantes; no importar bibliotecas de infraestructura ni escribir SQL.
- En `carta_model.py` reglas y tipos de dominio de carta; no usarlo como modelo ORM de SQLAlchemy. Las tablas y mapeos ORM de cartas, cuando correspondan, pertenecen a `adapters` (archivo nuevo allí solo si es indispensable y se justifica).
- En `cartas_ports.py` contratos de puertos necesarios para repositorios, imágenes y consultas a habilidades; no implementaciones ni clientes.
- `sql_carta_repository.py` conserva la persistencia relacional del submódulo; `mongo_carta_repository.py` maneja archivos GridFS, sin colección propia de metadatos; `imagen_carta_adapter.py` valida/transforma técnicamente los archivos, pero no escribe en PostgreSQL.
- `catalogo_module.py` registra/compone el módulo de catálogo cuando llegue la fase de API; no replicar esta composición en `main.py` y en el controlador.
- Las conexiones reutilizables existen solamente en `src/database/postgresql/connection.py` y `src/database/mongodb/connection.py`. No crear engines o clientes por cada solicitud ni una segunda capa de conexiones dentro de `gestion-cartas`.
- `src/shared/idempotencia/` es propietaria de las reglas comunes de idempotencia; `src/shared/validacion/` contiene únicamente validaciones realmente transversales, no toda la lógica específica de cartas.
- **Habilidades:** reutilizar `catalog_abilities` y verificar el seed existente `HAB-000`; no recrearlos en 1B. La estructura oficial todavía NO muestra `gestion-habilidades`; no crear ese directorio unilateralmente ni colocar lógica completa de creación de habilidades en `gestion-cartas`. Para esta historia, acceder a una habilidad existente por código a través de un puerto de consulta.
- **No renombrar ni desplazar módulos oficiales**, no crear `backend/app/`, `backend/scripts/`, `backend/infra/` ni otros árboles alternativos por copiar ejemplos anteriores.

**Advertencia de importación:** los directorios `gestion-cartas`, `gestion-ubicaciones`, `gestion-sesiones`, `motor-juego` y otros nombres con guiones provienen del árbol oficial, pero no son identificadores válidos para importaciones normales `from ... import ...` en Python. No inventar imports inválidos, no agregar modificaciones globales de `sys.path` ni renombrar a escondidas. En 1B.2A el usuario aprobó `importlib.import_module()` centralizado en `catalogo_module.py`, imports relativos internos y pruebas de composición/registro; no hay carga dinámica en dominio, puertos, servicios ni repositorios. Se conserva la estructura. Motivo, límites de análisis estático y separación ORM/dominio en [ORM_PERSISTENCE_1B2A.md](ORM_PERSISTENCE_1B2A.md). Alembic sigue sin importar estos modelos: metadata de seis tablas incompleta para todo el esquema.

### 2.2 Clean Code, documentación, seguridad y mantenibilidad

- Respetar los **nombres oficiales existentes en español** (`cartas_service.py`, `cartas_ports.py`, `carta_model.py`, etc.); para símbolos nuevos, usar nombres claros y consistentes con el módulo. Tablas y columnas SQL ya acordadas en inglés. Evitar traducciones arbitrarias y nombres duplicados para el mismo concepto. Documentación y docstrings pueden estar en español con terminología uniforme.
- Agregar anotaciones de tipos en las funciones y métodos propios, especialmente en fronteras públicas. Preferir nombres que expresen intención y contratos explícitos.
- **Documentación Clean Code obligatoria con cada cambio de código:** todo módulo Python nuevo debe tener una docstring de módulo que indique su propósito y límite de responsabilidad. Toda clase o función pública nueva o modificada debe disponer de docstring clara cuando su contrato no sea obvio; en este proyecto, exigir docstring para las funciones públicas de servicios, repositorios, validadores, infraestructura y scripts aunque su nombre sea expresivo. Una función privada no trivial también requiere docstring.
- Las docstrings deben explicar el **propósito**, parámetros cuando requieran interpretación, valor devuelto y errores/excepciones relevantes. Documentar especialmente precondiciones, invariantes, idempotencia, concurrencia y efectos secundarios (lectura/escritura de datos, archivos, transacciones). Evitar repetir literalmente la firma o narrar cada línea.
- **Clean Code no significa comentar todo:** el código debe ser autoexplicativo; los comentarios en línea se reservan para explicar el *porqué* de una decisión no evidente, limitación de dependencia o comportamiento delicado. No escribir comentarios redundantes como «incrementa contador» en una línea `counter += 1`.
- Una función implementa una sola responsabilidad cohesionada, con un nombre claro y nivel de abstracción uniforme. Extraer helpers únicamente si mejora legibilidad, reutilización o capacidad de prueba; evitar fraccionar operaciones simples en envoltorios vacíos.
- Al cambiar instalación/ejecución/pruebas, actualizar el `README.md` de la **raíz** y, si se requiere detalle del catálogo, este contrato o un documento dentro del repositorio aprobado. No asumir que existe `backend/README.md`. Registrar decisiones arquitectónicas significativas en un ADR; no sustituir ese registro con comentarios en código.
- **El cambio no está terminado si su documentación quedó desactualizada:** junto con el código entregar pruebas, docstrings, indicaciones de ejecución y, cuando aplique, contrato o ADR actualizado. La revisión debe comprobar código y documentación juntos.
- No añadir dependencias, librerías ni patrones sin justificar su uso.
- Cerrar correctamente sesiones y conexiones. Manejar y registrar fallos sin exponer contraseñas, trazas internas ni bytes de imágenes en logs.
- Las credenciales se cargan de variables de entorno. **Nunca** guardar `.env` con secretos en Git; sí mantener `.env.example` sin secretos reales.
- Todas las tablas SQL deben tener restricciones e índices explícitos y con nombres estables.
- Toda migración debe revisarse y probarse antes de aceptarla; no confiar ciegamente en la generación automática de Alembic.
- No alterar ni eliminar una carta utilizada por partidas antiguas. La estrategia futura de cambios será desactivación y/o versionado; **no** implementar aún un sistema de versiones completo.
- Mantener un archivo `README.md` con instrucciones reproducibles para levantar, migrar, probar y apagar el entorno.
- Evitar cambios ajenos a la fase asignada. No generar endpoints, frontend, lógica de combate o autenticación completa durante la primera fase.

---

## 3. Estructura oficial y correspondencia con Crear carta

La siguiente estructura es la **única distribución autorizada** para esta User Story. Se muestran los archivos y carpetas relevantes del árbol oficial facilitado por el equipo, no se pretende repetir cada módulo ajeno ni afirmar que su contenido ya funcione.

```text
Poke-Arena/
├── AGENTS.md                                  # Instrucciones existentes para Codex
├── .env.example                               # Variables de Docker/backend (ya previsto en raíz)
├── .gitignore
├── docker-compose.yml                         # Compose OFICIAL; no crear compose.yaml
├── README.md                                  # Instrucciones globales
├── ESTRUCTURA-REPOSITORIO.md                  # Referencia de arquitectura oficial
├── manage.py                                  # Entry point de gestión existente; inspeccionar antes de ampliar
├── backend/
│   ├── pyproject.toml                         # Dependencias y herramientas: respetar existente
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                             # Configuración de metadata y URL; conservar
│   │   ├── script.py.mako
│   │   ├── NOTA-IMPORTANTE.txt
│   │   └── versions/                          # Recuperar/verificar historial antes de sucesoras
│   ├── src/
│   │   ├── main.py                            # Entrada API; fuera de alcance inicial
│   │   ├── database/
│   │   │   ├── postgresql/connection.py        # Una fuente de engine/sesiones
│   │   │   ├── mongodb/connection.py           # Una fuente de Mongo client/DB
│   │   │   ├── explicacion_database.txt
│   │   │   └── outbox_worker.py               # Existente: no tocar en entregas 1A–1C
│   │   ├── shared/
│   │   │   ├── config.py                       # Configuración común del backend
│   │   │   ├── idempotencia/                   # Reglas compartidas; ampliar solo cuando corresponda
│   │   │   ├── validacion/                     # Validación transversal, sin lógica duplicada
│   │   │   ├── seguridad-roles/                # Autenticación/autorización en etapa posterior
│   │   │   ├── observabilidad/
│   │   │   ├── errores-rfc7807/
│   │   │   └── NOTA-IMPORTANTE.md
│   │   └── modules/
│   │       ├── nota-diseño.txt
│   │       └── catalogo/
│   │           ├── catalogo_module.py          # Composición y registro de catálogo; después
│   │           ├── gestion-cartas/
│   │           │   ├── controllers/
│   │           │   │   ├── cartas_controller.py # HTTP/router; fase posterior
│   │           │   │   └── cartas_dtos.py       # DTOs de entrada/salida; después
│   │           │   ├── domain/
│   │           │   │   └── carta_model.py       # Modelo de dominio, sin dependencias de DB
│   │           │   ├── ports/
│   │           │   │   └── cartas_ports.py      # Contratos/interfaces de dependencia
│   │           │   ├── services/
│   │           │   │   └── cartas_service.py    # Orquestación de Crear carta; después
│   │           │   └── adapters/
│   │           │       ├── sql_carta_repository.py
│   │           │       ├── mongo_carta_repository.py
│   │           │       └── imagen_carta_adapter.py
│   │           └── gestion-ubicaciones/          # Módulo independiente; no tocar
│   └── tests/
│       └── concurrency/                       # Existe; agregar pruebas solo con alcance explícito
└── frontend/                                  # NO modificar en esta fase
```

### 3.1 Destinos de cada componente (sin duplicar)

| Componente | Ubicación oficial | Responsabilidad / límite |
|---|---|---|
| Docker | `docker-compose.yml` de raíz | Servicios PostgreSQL y MongoDB y volúmenes |
| Variables de entorno | `.env.example` de raíz; `backend/src/shared/config.py` | Declaración de variables / lectura de configuración |
| Conexión SQL | `backend/src/database/postgresql/connection.py` | Engine, sesión, salud y cierre de recursos |
| Conexión Mongo | `backend/src/database/mongodb/connection.py` | Cliente, base y cierre de recursos |
| Migraciones | `backend/alembic/env.py`, `backend/alembic/versions/` | Esquema SQL, restricciones, `HAB-000` y contadores |
| Dominio de cartas | `backend/src/modules/catalogo/gestion-cartas/domain/carta_model.py` | Invariantes y conceptos de carta sin ORM |
| Contratos del feature | `.../gestion-cartas/ports/cartas_ports.py` | Interfaces que consume el servicio |
| Persistencia relacional | `.../gestion-cartas/adapters/sql_carta_repository.py` | Acceso SQL a cartas y contadores |
| Persistencia de imágenes | `.../gestion-cartas/adapters/mongo_carta_repository.py` | Archivos GridFS; metadatos autoritativos en SQL |
| Procesamiento de imagen | `.../gestion-cartas/adapters/imagen_carta_adapter.py` | Validación técnica y miniatura; NO SQL |
| Caso de uso | `.../gestion-cartas/services/cartas_service.py` | Orquestación e idempotencia mediante puertos |
| Entrada HTTP | `.../gestion-cartas/controllers/cartas_controller.py` | Endpoint y autorización; fase posterior |
| DTOs | `.../gestion-cartas/controllers/cartas_dtos.py` | Datos de entrada/salida HTTP; fase posterior |
| Idempotencia reutilizable | `backend/src/shared/idempotencia/` | Reglas y modelos compartidos, no duplicar en cartas |
| Pruebas | `backend/tests/` | Unitarias, integración, concurrencia; respetar configuración |
| Documentación | `README.md` raíz, `AGENTS.md` raíz y contrato | Ejecución, reglas del agente, diseño |

**Expansiones permitidas con justificación:** se pueden añadir archivos dentro de los directorios oficiales si existe una responsabilidad nueva realmente necesaria (por ejemplo, un mapper/ORM SQL en `adapters/` distinto del modelo de dominio, o bootstrap idempotente en `src/database/mongodb/`). No se permite crear un árbol arquitectónico paralelo ni una feature distinta para un mismo comportamiento.

**Situación de habilidades:** `catalog_abilities` y `HAB-000` ya existen; reutilizar y verificar su representación antes de cualquier ampliación. No hay carpeta oficial `gestion-habilidades`, por lo que su caso de uso de creación permanece fuera del alcance. El acceso de lectura necesario para Crear carta debe mantenerse detrás de un puerto y de su adaptador; cuando el equipo defina la estructura de habilidades, se moverá a su responsable sin romper el dominio.

**Atención a la diferencia de conceptos:** `carta_model.py` describe el **dominio**, mientras que las definiciones SQLAlchemy/DDL describen **persistencia**; no transformar el dominio en un modelo dependiente de la base únicamente para reutilizar el nombre.

## 4. Contrato de PostgreSQL: reutilización aprobada

### 4.1 Estado auditado y convenciones

- Base actual: **`pokearena_db`**. No se aprueba renombrarla.
- Revisión registrada: **`008_flex_card_img_dims`**; doce tablas, sin columnas identity. Los IDs de entidades se conservan como `VARCHAR(36)`; no asumir que el tipo SQL es UUID.
- Fechas existentes `TIMESTAMPTZ`; usar UTC. Mantener `CHECK`, FKs e índices con nombres estables; no sustituirlos por ENUM ni generar índices duplicados por inercia.
- No borrar contenido histórico ni reemplazar tablas para hacerlas coincidir con un diseño nuevo. Preservar `catalog_cards_legacy_002`, `catalog_card_migration_issues`, `catalog_locations`, `identity_users`, `identity_sessions` y `alembic_version`.
- Códigos canónicos y reglas de dominio en el módulo de catálogo; equivalencia con restricciones SQL verificada mediante pruebas. No crear una segunda definición transversal innecesaria.

| Responsabilidad lógica de v1.2 | Tabla física que se conserva |
|---|---|
| cards | `catalog_cards` |
| abilities | `catalog_abilities` |
| card_code_counters | `catalog_card_code_counters` |
| idempotency_requests | `shared_idempotency_records` |
| Metadatos y estado de imágenes | `catalog_card_images` |
| Eventos durables | `shared_outbox` |

Los nombres lógicos no son instrucciones para crear otras tablas ni vistas duplicadas.

### 4.2 `catalog_abilities`

**Esquema existente que se reutiliza:**

| Columna | Tipo / regla existente |
|---|---|
| `id` | `VARCHAR(36)`, PK |
| `code` | `VARCHAR(7)`, UNIQUE, NOT NULL; formato `HAB-[0-9]{3}` |
| `name` | `VARCHAR(100)`, NOT NULL |
| `ability_type` | `VARCHAR(30)`, NOT NULL |
| `description` | `VARCHAR(500)`, NOT NULL, default cadena vacía |
| `params` | JSONB, NOT NULL |
| `has_effect` | BOOLEAN, NOT NULL, default TRUE |
| `evolution_target_card_id` | `VARCHAR(36)`, nullable; FK a `catalog_cards.id`, ON DELETE RESTRICT |

`HAB-000` existe una sola vez con nombre `Sin Habilidad`, `ability_type='HAB-000'`, `has_effect=false`, `params={}` y destino de evolución nulo. Conservar su ID y sus referencias. La restricción reservada existente no valida toda la semántica de habilidades.

**Pendiente:** contrato completo de disparadores, condiciones, efectos, objetivos, JSON y prevención de ciclos. Las columnas propuestas en v1.2 (`is_noop`, `trigger_type`, etc.) no son cambios aprobados. No reinterpretar automáticamente `params`, inventar un módulo `gestion-habilidades` ni implementar Crear habilidad dentro de Crear carta. Consultar habilidades existentes por código mediante puerto.

### 4.3 `catalog_cards`

| Columna | Tipo / regla existente |
|---|---|
| `id` | `VARCHAR(36)`, PK |
| `code` | `VARCHAR(30)`, UNIQUE, NOT NULL; código público inmutable |
| `name` | `VARCHAR(100)`, NOT NULL; longitud tras trim 1–100 |
| `cost` / `power` | SMALLINT, NOT NULL; 0–10 / -20–20 |
| `card_type` | `VARCHAR(3)`, NOT NULL; FUE, AGU, PLA, ELE, PSI, LUC |
| `rarity` | `VARCHAR(20)`, NOT NULL; COMUN, POCO_COMUN, RARA, LEGENDARIA |
| `ability_id` | `VARCHAR(36)`, NOT NULL; FK a `catalog_abilities.id`, ON DELETE RESTRICT |
| `image_id` | `VARCHAR(36)`, nullable y UNIQUE; FK a `catalog_card_images.id`, ON DELETE RESTRICT |
| `version` | BIGINT, NOT NULL, default 1; CHECK >=1; **es versión, no PK** |
| `created_at` | TIMESTAMPTZ, NOT NULL |

Conservar el CHECK que vincula `code` con `card_type` y el rango 001–999. Existe trigger `trg_catalog_cards_code_immutable`, que usa `prevent_catalog_card_code_change()`. No editar código ni tipo en el caso de uso inicial. Reutilizar índices por `card_type` y `rarity`; evaluar un índice `ability_id` según consultas, sin crearlo en esta fase.

**Publicación:** una carta sin `image_id`, sin registro de imagen, sin estado `READY` o sin ambos archivos verificados no está disponible para jugadores. El estado autoritativo es `catalog_card_images.state`; no añadir `catalog_cards.image_status` como copia. La exposición futura de `image_status` en un DTO será derivada de esa fuente. No suponer que una FK o un estado SQL prueba la existencia de bytes en GridFS.

No existen `is_active` ni `updated_at` en esta tabla. La política de desactivación y evolución histórica sigue pendiente; no agregarlos automáticamente por la versión anterior del contrato.

### 4.4 `catalog_card_code_counters`

| Columna | Tipo / regla existente |
|---|---|
| `card_type` | `VARCHAR(3)`, PK; seis abreviaturas aprobadas |
| `last_value` | INTEGER, NOT NULL, default 0; CHECK 0–999 |

Conservar las seis filas y su valor confirmado. La auditoría observó `PLA=1` y el resto en 0; esos valores son evidencia, no un seed a imponer. Solo una base vacía reproducida mediante historial verificado comienza con contadores iniciales, considerando las reservas históricas que definan las migraciones.

La futura creación debe bloquear/actualizar el contador, insertar carta y registrar idempotencia en una transacción. No usar `MAX(id)+1`, contadores en memoria ni reiniciar filas existentes. Agotamiento de 999 produce error de negocio; rollback no consume número; una carta confirmada pendiente o fallida conserva su código y los reintentos reutilizan ese recurso.

### 4.5 `shared_idempotency_records`

Responsabilidad compartida en `backend/src/shared/idempotencia/`; no crear `idempotency_requests` ni una segunda implementación en catálogo.

| Columna | Tipo / regla existente |
|---|---|
| `id` | `VARCHAR(36)`, PK |
| `actor_id` | `VARCHAR(128)`, NOT NULL |
| `operation` | `VARCHAR(200)`, NOT NULL |
| `idempotency_key` | `VARCHAR(128)`, NOT NULL |
| `request_hash` | `VARCHAR(64)`, NOT NULL |
| `resource_id` | `VARCHAR(36)`, nullable |
| `endpoint` | `VARCHAR(200)`, NOT NULL |
| `response_status` / `response_body` | INTEGER / JSONB, ambos presentes o ambos nulos |
| `created_at` | TIMESTAMPTZ, NOT NULL |

Conservar UNIQUE `(actor_id, operation, idempotency_key)` y las respuestas almacenadas. Requisito del caso de uso: mismo actor/operación/clave/contenido devuelve el mismo recurso o reanuda; contenido distinto produce conflicto; concurrencia no duplica carta ni consume otro código. El hash normalizado debe incluir el hash del original.

**Pendiente:** representación de progreso, recuperación de solicitudes abandonadas y retención. No existen `status`, `updated_at` ni `expires_at`; no afirmar que están implementados ni añadirlos por anticipación. La ventana de al menos siete días de v1.2 queda como propuesta operativa por confirmar. No purgar registros necesarios para reintentos/reconciliación ni reescribir sus respuestas históricas.

### 4.6 `catalog_card_images`: fuente de verdad aprobada

| Grupo | Columnas existentes / reglas |
|---|---|
| Identidad | `id VARCHAR(36)` PK; asociación desde `catalog_cards.image_id` |
| Original | `original_storage_key VARCHAR(512)`, `original_sha256 VARCHAR(64)`, `image_format VARCHAR(10)`, `byte_size INTEGER`, `width`, `height`; NOT NULL |
| Miniatura | `thumbnail_storage_key VARCHAR(512)`, `thumbnail_format VARCHAR(10)`, `thumbnail_byte_size`, `thumbnail_width`, `thumbnail_height`; nullable mientras no esté lista |
| Procesamiento | `state VARCHAR(20)` default PENDING; `attempts`, `generation` INTEGER >=0 |
| Recuperación | `lease_token VARCHAR(36)`, `lease_expires_at`, `next_attempt_at`, `sanitized_error VARCHAR(500)` |
| Fechas | `created_at`, `updated_at` TIMESTAMPTZ, NOT NULL |

Estados existentes: `PENDING`, `PROCESSING`, `RETRY_PENDING`, `READY`, `FAILED`. Preservar su significado; `RETRY_PENDING` es recuperable, no publicable. `READY` exige metadatos de miniatura WebP 200x280 y referencia no nula; además, el futuro adaptador debe verificar ambos archivos reales antes de confirmar disponibilidad.

El esquema valida original PNG/JPEG/WebP, hash hexadecimal de 64 caracteres y tamaño 1–5 000 000 bytes. **Diferencia entre revisiones:** la base original en 008 permite mínimo 300x420 y tolerancia de proporción. La sucesora 1B.2B exige mínimo 600x840, proporción exacta 5:7 y tamaño y dimensiones de miniatura presentes en READY. El inventario y la validación están en [SCHEMA_ALIGNMENT_1B2B.md](SCHEMA_ALIGNMENT_1B2B.md).

Las referencias `original_storage_key` y `thumbnail_storage_key` deberán resolver archivos GridFS. **Pendiente:** formato, tipo de ID GridFS, compatibilidad con claves locales previas, integridad y transición. No se aprueba añadir columnas ni otra tabla de metadatos. Los metadatos internos obligatorios de GridFS se usan técnicamente sin convertirlos en una segunda autoridad de estado de negocio.

### 4.7 Historial Alembic: recuperación antes de sucesoras

**Hechos auditados:**

- `8a9e309` (2026-10-24) incorporó `008_flexible_card_image_dimensions.py`, revisión `008_flex_card_img_dims`, hija de `007_cards_without_image`.
- 007 permitió cartas con `image_id` nulo; 008 relajó dimensiones/proporción.
- `02a2b89` añadió `009_location_extended_fields`, posterior a 008 y ajena al alcance de Crear carta.
- `4843809` (2026-11-05), incluido en HEAD auditado `988a567`, eliminó del árbol las revisiones 001–009 y la implementación anterior. En la auditoría previa los archivos seguían recuperables en Git y `versions/` contenía solamente `.gitkeep`; 1B.1 recuperó ahora 001–008 sin modificaciones.
- La base registra 008 y su esquema observado coincide con los cambios relevantes inspeccionados. No se conoce el ejecutor original. En 1B.1 se verificó la reproducción completa hasta 008 en bases aisladas y su correspondencia estructural con la fuente.

**Condición histórica satisfecha en 1B.1:** archivos recuperados, dependencias revisadas, cadena reproducida en bases aisladas y esquema contrastado con 008. Evaluar 009 por separado sin aplicarla automáticamente ni alterar ubicaciones. Solo con autorización posterior de 1B.2B se podrán evaluar ajustes o sucesoras sobre tablas existentes. No modificar revisiones ya aplicadas ni inventar una inicial sustituta. No usar `stamp head` para ocultar divergencias ni `autogenerate` con metadata vacía/incompleta.

Los inicializadores de motores pueden administrar usuarios/bases, pero no duplicar DDL de Alembic. Respaldar y comprobar restauración antes de aplicar cambios autorizados sobre datos conservados.

## 5. MongoDB GridFS, proyección y consistencia

### 5.1 Distribución de responsabilidades aprobada

| Componente | Autoridad y límite |
|---|---|
| `catalog_cards` | Entidad, código, atributos y relaciones SQL |
| `catalog_card_images` | Referencias, hash, formatos, dimensiones, tamaños, estado y recuperación |
| GridFS | Almacenamiento físico del original y miniatura en volumen local persistente |
| `pokearena_catalog.cards_projection` | Proyección existente de consulta; conservar documentos e índices |
| `shared_outbox` | Eventos durables existentes; conservar filas, versiones y estado |

No crear una colección propia Mongo `card_images` ni otro catálogo de metadatos de imágenes. Las colecciones internas `<bucket>.files` y `<bucket>.chunks` forman parte de GridFS y deben gestionarse mediante su API.

**Diseño 1C validado en aislamiento.** Usar `MONGO_GRIDFS_BUCKET=card_assets` en `MONGO_DB` mediante la conexión oficial PyMongo Async. Las referencias son cadenas `gridfs:<ObjectId>`. La ampliación de permisos originales y cualquier transición de referencias previas requieren revisión separada. Véase [GRIDFS_IMAGE_STORAGE_1C.md](GRIDFS_IMAGE_STORAGE_1C.md).

### 5.2 Proyección y Outbox conservados, sin activación nueva

La auditoría encontró `pokearena_catalog.cards_projection` con índices `_id`, texto en `name`, `card_type`, `cost` y UNIQUE `code`. La decisión de evitar metadatos redundantes no autoriza borrar esta proyección de catálogo.

`shared_outbox` conserva eventos JSONB, agregado/versiones, correlación, estado y mecanismos de intentos/lease. Mantener UNIQUE `(aggregate_type, aggregate_id, aggregate_version)` e índices existentes. Un evento figuraba PROCESSED; esto no demuestra que el worker actual funcione.

`backend/src/database/outbox_worker.py` es el punto de entrada independiente de 1F. Reclama únicamente eventos CardCreated y publica en `cards_projection` usando la versión del agregado. Se mantiene fuera de FastAPI y restringido al entorno aislado. Véase [el informe 1F](CARD_CREATION_OUTBOX_1F.md).

### 5.3 Requisitos funcionales de imágenes conservados

1. Validar original antes de crear carta: PNG/JPEG/WebP por contenido, archivo legible y máximo **5 000 000 bytes**. Extensión no acredita formato.
2. Normalizar orientación EXIF cuando corresponda y validar después mínimo **600x840** y proporción exacta **7 × width = 5 × height**. No deformar ni aceptar tolerancia arbitraria.
3. Generar miniatura WebP legible **200x280**, conservando proporción; limitar memoria/dimensiones de decodificación.
4. Conservar original y miniatura físicamente en GridFS y registrar referencias/metadatos en SQL, sin colección redundante.
5. No cargar binarios en listados. Diseñar acceso controlado por backend en fase API.
6. Marcar `catalog_card_images.state=READY` únicamente tras verificar existencia y recuperación de ambos archivos; una carta sin imagen permanece no disponible para jugadores.

Los adaptadores 1C validan, generan y verifican ambos archivos. 1D coordina el estado SQL y devuelve la creación confirmada desde Python. 1E expone el servicio por API y la proyección corresponde a 1F.

### 5.4 Consistencia entre motores: invariantes y decisiones pendientes

SQL y GridFS no comparten transacción. 1D reserva los dos IDs en SQL antes de escribir en GridFS y verifica ambos archivos en la misma invocación. Una transacción posterior confirma la creación y su evento. El protocolo, la recuperación y el alcance de la compensación se detallan en [el informe 1D](CARD_CREATION_SERVICE_1D.md).

Invariantes exigidas para cualquier estrategia:

- Solicitud e imagen inicialmente inválidas no crean carta ni consumen código.
- Contador, carta e idempotencia deben coordinarse transaccionalmente en SQL. Un reintento conserva IDs y código.
- Fallo parcial de almacenamiento no permite publicar la carta; conservar estado recuperable o fallido en `catalog_card_images`.
- Si GridFS confirma archivos pero SQL no confirma sus referencias/estado, la reconciliación deberá resolver el resultado sin duplicar recursos ni borrar archivos posiblemente referenciados.
- Verificar referencias y resultado de commits inciertos antes de compensar. Las futuras limpiezas requieren política de conservación e idempotencia.
- Toda lectura de jugadores, incluida la proyección, debe respetar la disponibilidad confirmada; acordar propagación y fallos antes de habilitar escrituras o procesos.

No se especifica ahora un orden operativo de commits/I/O como si estuviera aprobado. No activar un reconciliador ni un worker por el solo hecho de describir estas invariantes.

### 5.5 Preparación futura de GridFS

En fase 1C autorizada, preparar/verificar bucket e índices internos mediante API del driver, usando conexión oficial y usuario de aplicación con privilegios mínimos. No crear índice `card_images.card_id` ni bootstrap de metadatos redundantes. Si hace falta bootstrap explícito, integrarlo en `manage.py` o `src/database/mongodb/`, sin `backend/scripts/`.

Debe ser idempotente y conservar colección e índices de proyección. Las pruebas escribirán solo archivos identificados de una base/bucket aislados; nunca limpiar colecciones productivas. El contrato exacto SQL/GridFS debe aprobarse antes de escribir referencias.

## 6. Infraestructura conservada y deriva auditada

### 6.1 Motores, servicios y volúmenes

| Servicio oficial | Versión aprobada | Volumen activo observado | Montaje |
|---|---|---|---|
| `postgres` | PostgreSQL 16, `postgres:16-alpine` | `pokearena_pgmaster_data` | `/var/lib/postgresql/data` |
| `mongo` | MongoDB 7, `mongo:7.0` | `pokearena_mongo_data` | `/data/db` |

**Deriva resuelta en 1A:** Compose usa `pokearena_pgmaster_data`, `pokearena_mongo_data`, el volumen config Mongo identificado y la red existente, todos externos. La recreación autorizada retiró solo los dos binds de inicialización obsoletos y aplicó loopback/healthchecks autenticados sin sustituir datos. Revalidar inventario y respaldos antes de otra operación.

Conservar `docker-compose.yml` de raíz como definición oficial; no crear otro Compose, Dockerfile ni API. Puertos de desarrollo en loopback, healthchecks efectivos y autenticados, persistencia local y credenciales de aplicación con privilegios mínimos siguen siendo criterios futuros. Los motores observados saludables no prueban restauración, persistencia tras reinicio ni permisos correctos de FastAPI.

En el cierre de 1A se verificó uso ordinario de `poke_api_user` y `poke_api_mongo`; administración solo para operación/healthchecks. Se renovó el rol SQL existente y se creó la cuenta Mongo con rol local restringido. No se alteraron los otros roles SQL ni el rol separado de migración; no se ejecutó Alembic.

### 6.2 Configuración y comandos

Conservar `.env.example` de raíz, `.gitignore`, `backend/src/shared/config.py` y conexiones oficiales. Nombres actuales `DATABASE_URL`, `MONGO_URL`, `MONGO_DB` y variables Compose compatibles; no imponer `MONGO_URI` por documentación anterior. No renombrar bases ni variables unilateralmente. `.env` privado, sin secretos en logs/documentos; verificar resolución de su ruta al ejecutar desde `backend/`.

Las variables de inicialización no actualizan automáticamente usuarios de volúmenes existentes. El backend se ejecuta inicialmente en el host; distinguir `localhost` de nombres de servicio dentro de Docker.

**En la fase D:** solo lectura/edición documental y comprobaciones locales. No ejecutar arranques, reinicios, bootstrap ni Alembic. En fases futuras, documentar comandos reales una vez reconciliadas la configuración y la cadena histórica; no prescribir ahora `alembic upgrade head` sobre la base conservada. Nunca usar `docker compose down -v` para reiniciar ni aplicar downgrade destructivo sobre datos reales sin autorización explícita.

### 6.3 Resultado final de 1A (2026-11-06)

La autorización posterior permitió completar las cuentas técnicas y recrear únicamente PostgreSQL y MongoDB retirando los dos binds de inicialización ausentes. Su contenido ya no era legible; se verificaron destinos initdb.d y uso exclusivo en entrypoints oficiales con datos vacíos, mientras las bases existentes estaban inicializadas. No se recuperaron scripts ni se ejecutó inicialización.

Antes de cambiar servicios se verificaron hashes de respaldos y la evidencia de restauración/persistencia aisladas. Se conservaron exactamente las imágenes locales 16/7, los tres volúmenes activos, red y puertos. El primario conserva identidad de clúster, configuración de replicación, cero réplicas conectadas/slots y estado fuera de recuperación. `pokearena_pgreplica_data` no se montó ni modificó. No se acredita failover ni una réplica futura por esta prueba.

**Permisos SQL:** `poke_api_user` tiene CONNECT a `pokearena_db`, USAGE de public; SELECT en `catalog_abilities`; SELECT/UPDATE en contadores; SELECT/INSERT/UPDATE en cartas, imágenes, idempotencia y Outbox. Sin superusuario, creación de bases/roles/esquema, replicación, bypass RLS, membresía de migrador ni DELETE/TRUNCATE sobre esas tablas. No había consumidores activos incompatibles detectados antes de rotar la contraseña; otros clientes desconocidos quedan fuera de esa observación.

**Permisos Mongo:** `poke_api_mongo` autentica en `pokearena_catalog`, con rol local `pokearena_app_catalog` limitado a find/insert/update/listIndexes sobre `cards_projection`; sin administración global ni permisos en otras bases. No se crearon colecciones de negocio, buckets ni permisos GridFS anticipados. Antes de ampliar permisos, acordar bucket/recursos y obtener autorización; el diseño definitivo de GridFS sigue en 1C.

Secretos aleatorios guardados únicamente en `.env` privado; URLs habilitadas tras comprobar credenciales. Los healthchecks aplicados usan administración operativa; las conexiones de FastAPI usan exclusivamente las cuentas técnicas. Se retiraron de Compose las variables de aplicación innecesarias una vez eliminados los inicializadores.

**Verificaciones exitosas:** ambos servicios healthy, ocho pruebas de configuración, Compose válido, `git diff --check`, conexiones oficiales desde raíz/backend sin overrides administrativos, ausencia de privilegios administrativos y HTTP 200 de `/api/v1/health` con ambas bases connected. El proceso HTTP de prueba se cerró limpiamente; las bases siguen ejecutándose. Filas de las cuatro bases SQL y documentos/índices de proyección Mongo intactos; estructura SQL excluyendo ACL deliberadamente cambiadas coincide con el clon restaurado. No se ejecutaron escrituras de negocio, migraciones ni worker.

Evidencia privada: respaldos originales en `docker-data/backups/1a-20261106/`; cierre en `docker-data/backups/1a-20261106-completion/`. Los respaldos preceden la rotación, por lo que una restauración futura debe reconciliar cuentas con `.env` bajo autorización. No se validó instalación en volúmenes vacíos. Ruff/Mypy e httpx declarados no están instalados; no se modificaron dependencias. El diagnóstico HTTP usó biblioteca estándar. Comandos y detalle en README.

### 6.4 Resultado de 1B.1

Ocho revisiones originales recuperadas desde `8a9e309`, con hashes/commits en `backend/alembic/history_manifest.json`; 009 excluida. Sin dependencias de código de negocio eliminado. Configuración `MigrationSettings` independiente de Mongo/API, URL explícita, rol no administrativo y guard de bases aisladas. Rutas nativas basadas en `%(here)s` y `path_separator=os` (Alembic >=1.16; probado con 1.20.1). No se importan ORM ni módulos con guiones; no se autoriza autogenerate, ni SQL offline de la cadena que inspecciona tablas.

Reconstrucciones independientes desde raíz y backend hasta 008: 12 tablas, 103 columnas, 50 constraints, 27 índices, cuatro FKs, una función y un trigger; cero diferencias estructurales normalizadas con la fuente, excluyendo propietarios/ACL deliberadamente distintos. Suite final: 24 pruebas aprobadas, incluida integración real. Bases/servicios originales sin cambios; instancia de prueba detenida, volumen nuevo conservado. No se ejecutó Alembic sobre pokearena_db ni se cambiaron permisos de API. Informe, comandos y límites: [ALEMBIC_RECOVERY_1B1.md](ALEMBIC_RECOVERY_1B1.md).

## 7. Fases y criterios de aceptación

La autorización vigente cubre 1C en bases aisladas. La aplicación de la sucesora 1B.2B a la base original sigue pendiente.

### D — Actualización documental (completada)

- Cambiar solo `AGENTS.md` y este contrato.
- Registrar decisiones aprobadas, hechos auditados, pendientes y fases sin confundirlos con implementación.
- Comprobar coherencia entre ambos textos y alcance de archivos, sin pruebas que escriban datos.

### 0 / 1B.1 — Recuperación y verificación Alembic (validada; informe complementario)

- Recuperar revisiones del historial Git en `backend/alembic/versions/`, revisar dependencias y metadata sin modificar revisiones aplicadas.
- Verificar cadena y reproducción en base aislada; contrastar estado 008 con esquema conservado y separar evaluación de 009 de ubicaciones.
- Resolver estrategia de importación con guiones antes de ejecutar módulos afectados; no renombrar carpetas ni introducir hacks de `sys.path`.
- **Aceptar solo con** trazabilidad documentada, diferencias identificadas y ausencia de cambios en la base conservada. No proponer sucesoras hasta terminar esta verificación.

### 1A — Alineación de infraestructura (completada; evidencia en §6.3)

- Revisar Compose, variables, credenciales y conexiones oficiales preservando motores 16/7 y volumen real; proponer archivos exactos antes de editar.
- **Aceptar solo con** configuración validada, correspondencia explícita de volúmenes, conexión/healthchecks adecuados, permisos mínimos y persistencia/restauración verificadas bajo escenario autorizado.
- No crear tablas, endpoints, conexiones duplicadas ni procesos nuevos; no tocar frontend o worker.

### 1B.2A — ORM y persistencia (autorizada)

- Seis modelos ORM en adaptadores de catálogo y propietarios compartidos, dominio puro, puertos, repositorio SQL asíncrono y composición centralizada. No implementar todavía servicios/controladores.
- Reutilizar conexión/fábrica oficiales. El llamador abre un `BEGIN` explícito y controla su cierre. El repositorio rechaza `AUTOBEGIN` y hace flush sin commit, rollback ni cierre. Los errores técnicos sanitizados podrán traducirse al dominio más adelante.
- Verificar esquema real, relaciones, restricciones, sesiones, transacciones y ausencia de duplicados en pruebas aisladas preparadas con originales 001–008.
- Metadata parcial: no habilitar autogenerate, DDL ORM ni cambios de esquema. Informe y pruebas en [ORM_PERSISTENCE_1B2A.md](ORM_PERSISTENCE_1B2A.md).

### 1B.2B — Compatibilidad SQL/sucesoras (validada en aislamiento)

- Proponer ajustes mínimos exclusivamente sobre tablas existentes y responsabilidades aprobadas; sin PK BIGINT, nombres nuevos paralelos ni reinicio de contadores.
- La propuesta debe resolver únicamente pendientes autorizados, incluyendo discrepancia de imágenes si corresponde, con evaluación de datos y conservación histórica.
- Aplicar sucesoras solo después de revisar y autorizar su contenido y destino. ORM en adaptadores conforme a la regla de dominio puro; no crear una arquitectura alternativa.
- **Aceptar solo con** pruebas aisladas de restricciones, FKs, seeds, concurrencia e idempotencia pertinentes; verificar IDs, códigos, contadores, referencias y conservación antes/después. No afirmar aceptación por mera generación de migración.

### 1C — Integración técnica GridFS (validada en aislamiento)

- Tras aprobar base/bucket y representación de referencias, reutilizar conexión Mongo y adaptadores oficiales; SQL sigue siendo autoridad de imágenes.
- **Aceptar solo con** almacenamiento/recuperación de original y miniatura en entorno aislado, referencias verificables, persistencia local y preparación idempotente sin colección propia de metadatos.
- Preservar proyección, Outbox e índices existentes. No activar workers, reconciliadores ni caso de uso productivo por esta fase.

### 1D — Caso de uso Crear carta (validado en aislamiento)

El servicio compuesto en `catalogo_module.py` reutiliza la idempotencia y el Outbox compartidos. La reserva queda en SQL, los archivos se verifican en GridFS y la transacción final confirma los efectos de la creación. Véase [el informe 1D](CARD_CREATION_SERVICE_1D.md).

### 1E — API (validada en aislamiento)

Crear Carta usa `POST /api/v1/content/cards` con sesión de plataforma y rol administrativo. Se conserva 1D y se verifica OIDC localmente con firmas RSA. La validación con Google real y el despliegue original siguen pendientes. Véase [el informe 1E](CARD_CREATION_API_1E.md). La publicación por proyección requiere autorización independiente.

### 1G — Cierre de Crear Carta en aislamiento

La revisión `1g_local_master_admin` permite aprovisionar un único administrador LOCAL y conserva el esquema de catálogo. FastAPI expone el login local, revocación y lectura administrativa de habilidades. La operación, imágenes y proyección mantienen los contratos de 1C–1F. Véase [el informe 1G](CARD_CREATION_FINAL_1G.md) y [el contrato para React](CARD_CREATION_FRONTEND_HANDOFF.md).

### 3 — Integración full stack (pendiente de autorización)

Integrar `frontend/src/web-admin/modules/catalogo/` reutilizando componentes, hook y servicio existentes. No crear otro frontend. Mantener fuera de fases 0–1C `gestion-ubicaciones`, `identidad`, `motor-juego`, `torneos` y frontend, salvo alcance adicional explícito.

## 8. Pruebas específicas que deben desarrollarse en etapas posteriores

- **Concurrencia:** dos administradores crean cartas del mismo tipo a la vez → códigos diferentes.
- **Idempotencia:** mismo actor + operación + clave + contenido → una sola carta; misma clave con distinto contenido → conflicto.
- **Límite de códigos:** al llegar a 999 no se produce `PKA-FUE-1000`.
- **Rechazo temprano:** imagen inválida → ninguna carta insertada.
- **Fallo de GridFS:** PostgreSQL no publica carta sin ambas imágenes; reintento continúa el mismo recurso.
- **Fallo tras guardar imágenes:** reconciliación evita duplicados/archivos huérfanos permanentes.
- **Relaciones:** toda carta posee una habilidad válida, incluida `HAB-000`.
- **Evolución:** no se permiten autorreferencias ni ciclos entre cartas.
- **Seguridad:** sin sesión → 401; sesión sin rol admin → 403.
- **Integridad de lectura:** solo cartas con imagen SQL en READY y ambos archivos confirmados aparecen para jugadores; la política de desactivación queda pendiente.
- **Arquitectura:** las dependencias hexagonales se respetan, el dominio no importa infraestructura, no hay lógica SQL en controladores y no se modificó la estructura oficial sin autorización.

---

## 9. Decisiones pendientes y límites de aprobación

Las decisiones de §1.2 están aprobadas. Los siguientes detalles **no** lo están y requieren revisión antes de la fase dependiente:

| Pendiente | Condición previa / límite |
|---|---|
| Sucesoras después de 1B.1 | Historial reproducido y comparado; sucesora de imágenes validada en aislamiento. La aplicación a la base original requiere autorización independiente. 009 de ubicaciones sigue excluida. |
| Imports con guiones | Aprobado en 1B.2A: importlib solo en composición, imports relativos internos, sin renombrar ni modificar sys.path; probar composición/registro y documentar límites. |
| Discrepancia ORM en notas oficiales | Resuelta en 1B.2A por autorización explícita: dominio puro y mapeos en adaptadores; anotaciones documentales corregidas, topología preservada. |
| Referencias SQL/GridFS | Referencias `gridfs:<ObjectId>` y bucket `card_assets` validados en aislamiento. Pendientes los permisos originales y la transición desde archivos locales. |
| Procesamiento y recuperación | 1D valida el procesamiento en la misma invocación, los reintentos y la compensación controlada. Pendientes la conciliación operativa y la traducción a HTTP. |
| Publicación y proyección | Precisar actualización versionada y tratamiento de fallos para impedir exposición de imágenes incompletas. Conservar la proyección actual. |
| Idempotencia | 1D recupera el progreso con la misma clave y contenido. Pendientes la retención y la conciliación de respuestas históricas. |
| Habilidades | Completar disparadores/condiciones/efectos/objetivos, JSON y ciclos sin reinterpretar `params` ni crear funcionalidad ajena a esta historia. |
| Conservación histórica | Definir desactivación/versionado/snapshots antes de editar cartas o habilidades usadas. No imponer `is_active` automáticamente. |
| Operación posterior a 1A | 1A está cerrada; nuevas recreaciones/rotaciones requieren alcance explícito y revalidar respaldos, dependencias y privilegios. |

**ADRs futuros:** documentar almacenamiento SQL + GridFS y conservación de proyección; IDs VARCHAR(36), código y contador; estrategia de procesamiento y recuperación cuando sea elegida. Revisar el ADR histórico `docs/adr/ADR-002-create-card-images.md` recuperable en Git antes de crear registros nuevos; no sobrescribirlo ni imponer numeración/ubicación por anticipación.

Los requisitos de imagen estricta, unicidad, idempotencia, habilidad válida, autorización y publicación completa siguen vigentes aunque falte implementación. Un pendiente de diseño no habilita debilitar esos requisitos.

## 10. Definición de terminado y control de alcance

**La fase D termina** cuando ambos documentos coinciden con las diez decisiones aprobadas, distinguen estado actual y requisitos futuros, y solo se han editado esos dos documentos. No requiere ni autoriza pruebas con escrituras, conexiones operativas o migraciones.

**La preparación técnica futura solo termina** tras las autorizaciones y aceptación de 0, 1A, 1B y 1C: historial verificable, infraestructura conservada, compatibilidad SQL demostrada, GridFS con referencias SQL y pruebas repetibles en entornos aislados. No equivale a tener Crear carta, workers o frontend implementados.

Toda implementación futura debe entregar archivos modificados, decisiones, comandos exactos, pruebas realmente ejecutadas, riesgos y pendientes. Mantener docstrings, tipos, SOLID, DRY y documentación actualizada; actualizar README de raíz cuando cambie la ejecución. No anunciar como implementado o probado lo que solo está descrito aquí.

**Autorización vigente:** exclusivamente 1G en aislamiento. El despliegue original y el frontend requieren autorización independiente.

## 11. Documentación técnica de referencia

- Docker Compose, healthchecks y volúmenes: https://docs.docker.com/compose/gettingstarted/
- Imagen oficial de MongoDB e inicialización local: https://hub.docker.com/_/mongo
- Guía de Docker para PostgreSQL: https://docs.docker.com/guides/postgresql
- MongoDB GridFS: https://www.mongodb.com/docs/manual/core/gridfs/
- Alembic: revisión de migraciones autogeneradas: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- PyMongo síncrono y API asíncrona: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/

**Fuente funcional:** Poké-Arena, Caso de Negocio v1.3; Mapa de Epics, Features y User Stories; criterios de aceptación de «Crear carta» y «Crear habilidad». Las decisiones de §1.2 son aprobaciones explícitas del usuario posteriores a la auditoría, no texto literal del enunciado. Los detalles marcados pendientes no deben interpretarse como aprobados. Las fuentes funcionales referenciadas no fueron revalidadas como parte de esta actualización documental.
