# AGENTS.md — Poké-Arena

**Actualización documental:** 2026-11-09

**Ámbito:** repositorio completo de Poké-Arena (backend, frontend, datos, pruebas y documentación).
**Estado:** **US 3.1.1 — CI-5E, backend aprobado con observaciones**. CI-5C verificó el recorrido funcional con identidades de laboratorio. CI-5D concilió 80 cartas de `CI4-2026`, incluidas 20 comunes elegibles. Consultar el [contrato principal](backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md), el [contrato CI-5](backend/docs/contracts/CI_5_CONTRATO_AUDITORIA_FINAL_BACKEND.md) y el [informe de cierre](backend/docs/contracts/CI_5_INFORME_CIERRE_BACKEND.md).

**Alcance del cierre:** revisión y actualización documental. La integración React, las escrituras persistentes, los cambios de política de Identidad, la publicación y los trabajos posteriores requieren autorización independiente. Mantener fuera de las pruebas las bases originales y preservar las migraciones históricas.

**Línea base verificada:** FastAPI completó su ciclo de vida sin Motor. El PostgreSQL aislado `15433` está en 014, con el trigger de tipo permanente activo. El rol de aplicación puede actualizar la columna de apertura y tiene lectura e inserción en `cube_transactions`. Verificar mediante escritura solo en bases desechables.

> **Regla principal:** nunca confundir **estructura propuesta**, **archivo visto en un inventario**, **código existente**, **comportamiento probado** y **esquema aplicado**. La documentación de estructura recibida podría ser antigua. Antes de diseñar o editar, inspeccionar la rama y el árbol reales. Este AGENTS.md define reglas y prioridades, no certifica el estado del repositorio.

## 1. Autoridad, evidencia y alcance

1. Obedecer la **instrucción más reciente del usuario** y ejecutar únicamente la fase expresamente autorizada.
2. Consultar los requisitos oficiales (épicas, features, user stories y mapping), especialmente **US 3.1.1**, **US 1.1.1**, **US 1.1.3**, **US 2.1.1**, **US 3.1.2** y **US 3.1.3**. Las historias oficiales fijan el alcance funcional; no inventar criterios.
3. Leer `ESTRUCTURA-REPOSITORIO.md`, las notas técnicas existentes y los contratos aplicables de `backend/docs/contracts/`, pero **no asumir que están actualizados**.
4. Contrastar las afirmaciones documentales con el código, las pruebas, el historial de Git, las migraciones y —solo con autorización— el esquema SQL efectivo del ambiente correcto.
5. Si hay contradicciones, registrar **fuente, evidencia, alcance e impacto**. No reestructurar o sustituir código funcionando para hacerlo coincidir con un árbol de documentación.
6. Priorizar el reúso de componentes implementados, respetar los contratos de cada módulo y no adelantar funcionalidades de otras historias.

**Clasificación obligatoria de hallazgos:** `verificado en código`, `verificado por prueba ejecutada`, `verificado en base de datos`, `documentado/no verificado`, `presente en inventario`, `pendiente` o `no accesible`.

## 2. Estado conocido: no asumir integración sin comprobar

### 2.1. US 2.1.1 — Crear Carta

Según el informe final del equipo, **Crear Carta cuenta con backend y frontend implementados**, y una prueba exitosa de extremo a extremo desde React hasta PostgreSQL, GridFS y `cards_projection` mediante Outbox. Se reportaron además pruebas automatizadas con omisiones que dependían de motores reales.

- Backend reportado: Python 3.12, FastAPI, Pydantic, SQLAlchemy Async, Alembic, Pillow, PostgreSQL 16, MongoDB 7/GridFS, Outbox.
- Frontend reportado: React 18, TypeScript, Vite 5, Tailwind CSS, Fetch API y FormData.
- Identidad administrativa de demostración: token Bearer opaco y sesiones en PostgreSQL. **No confundirla con inicio de sesión de jugadores mediante Google.**
- Último reporte: rama `feature/crear-carta` publicada; el merge a otra rama no fue confirmado allí.

**No reimplementar ni refactorizar Crear Carta** para trabajar en Colección Inicial. Comprobar primero qué commits están realmente disponibles en la rama auditada.

### 2.2. Login Google: trabajo de otro integrante

El usuario informa que **un compañero ya implementó el inicio de sesión con Google**. El inventario de archivos compartido menciona `google_oidc.py` y `test_identity_google_login.py`. **Esto no demuestra por sí solo que el flujo esté fusionado, probado en producción, ni que disponga de creación de jugador y sesión utilizables.**

La auditoría debe revisar:

- Rama/commits donde se encuentra, relación con la rama activa y estado de integración; no hacer operaciones de Git que cambien el checkout.
- Ruta de autenticación, controlador, DTOs, servicio, puertos, adaptador Google y composición de `identidad_module.py`.
- Validación de tokens Google: firma, `iss`, `aud`, expiración y `sub`; configuración por ambiente, seguridad de secretos y errores. No usar el correo como identificador estable único del proveedor.
- Creación/recuperación de usuarios, asignación del rol jugador, idempotencia y concurrencia de primeros accesos, sesión propia de Poké-Arena y autorización posterior.
- Correspondencia entre usuario de Identidad, perfil del jugador, sesión y datos SQL; verificar qué crea realmente cada camino.
- Separación de login Google, login de administrador local y mecanismo de prueba no productivo de US 1.1.3.
- Punto de extensión para invocar un futuro caso de uso de entrega inicial **sin incrustar reglas de colección en el adaptador de Google**.
- Evidencia en pruebas, ambientes, scripts y migraciones; indicar explícitamente qué no está probado.

**No crear otro proveedor Google, otro sistema de sesiones ni reemplazar la implementación del compañero sin decisión arquitectónica y autorización.**

### 2.3. Migrations de jugadores

El inventario suministrado muestra `backend/alembic/versions/012_player_profiles_and_inventory.py`, además de `011_create_locations_full.py`, `010_local_master_admin.py`, `1b2b_card_image_integrity.py` y 001–008.

**Requisito especial:** antes de proponer tablas de colección, cubos, movimientos, entrega inicial o perfil, inspeccionar **la migración 012, sus revisiones anteriores (`revision`, `down_revision`), sus modelos correspondientes y su estado aplicado**. El nombre del archivo no prueba qué tablas contiene ni si está desplegada. Verificar si hay múltiples cabezas o ramas Alembic; no asumir una secuencia numérica lineal ni una revisión actual común a todos los ambientes.

## 3. Estructura de referencia: inventario compartido, sujeto a verificación

El árbol compartido del repositorio (posiblemente desactualizado) presenta **código fuente en nombres `snake_case`** y algunos directorios con guiones que contienen principalmente cachés Python. A efectos de la auditoría, la referencia inicial es:

```text
Poke-Arena/
├── AGENTS.md
├── ESTRUCTURA-REPOSITORIO.md
├── README.md
├── docker-compose.yml
├── manage.py
├── .env.example
├── backend/
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 1b2b_card_image_integrity.py
│   │       ├── 010_local_master_admin.py
│   │       ├── 011_create_locations_full.py
│   │       └── 012_player_profiles_and_inventory.py
│   ├── docs/contracts/
│   ├── src/
│   │   ├── main.py
│   │   ├── database/
│   │   │   ├── postgresql/{base.py,connection.py,revisiones.py}
│   │   │   ├── mongodb/{connection.py,destinos_outbox.py}
│   │   │   └── outbox_worker.py
│   │   ├── shared/{config.py,http_module.py,outbox.py,...}
│   │   └── modules/
│   │       ├── catalogo/
│   │       │   ├── catalogo_module.py
│   │       │   ├── gestion_cartas_bridge.py
│   │       │   └── gestion_cartas/
│   │       │       ├── controllers/
│   │       │       ├── services/
│   │       │       ├── domain/
│   │       │       ├── ports/
│   │       │       └── adapters/
│   │       ├── identidad/
│   │       │   ├── identidad_module.py
│   │       │   └── gestion_sesiones/
│   │       │       ├── controllers/sesiones_controller.py
│   │       │       ├── services/sesiones_service.py
│   │       │       ├── domain/sesion_model.py
│   │       │       ├── ports/sesiones_ports.py
│   │       │       └── adapters/{google_oidc.py,password_local.py,sql_sesiones.py}
│   │       └── jugadores/
│   │           ├── coleccion_mazos/
│   │           └── perfil_cuentas/
│   └── tests/
│       └── test_identity_google_login.py
└── frontend/
    ├── src/
    │   ├── shared/services/http-client.ts
    │   ├── web_admin/modules/{auth,catalogo}/
    │   ├── web_player/modules/
    │   │   ├── catalogo/
    │   │   └── vista_principal/
    │   └── portal_b2b/
    └── tests/
```

**No son rutas normativas hasta verificar en la rama activa.** Los directorios `gestion-cartas/`, `gestion-sesiones/`, `errores-rfc7807/` y `seguridad-roles/` también aparecen en el árbol compartido, pero allí se observan principalmente `__pycache__`; **no tratarlos como implementación fuente ni eliminarlos sin investigar**. Conservar `gestion_cartas_bridge.py` mientras no se comprenda su función; no sustituirlo por imports dinámicos, ni eliminarlo por presumir obsolescencia.

El manual de estructura recibido utiliza `gestion_cartas`, `gestion_sesiones`, `web_admin` y `web_player`; el inventario coincide en esas rutas de fuente. En caso de divergencia de rama, **el código rastreado en Git y sus imports válidos prevalecen para el diagnóstico**. Cualquier cambio de estructura requiere aprobación específica y actualización coordinada de pruebas y documentación.

### Exclusiones del inventario arquitectónico

No deducir arquitectura de `backend/.venv/`, `node_modules/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`, `docker-data/backups/` ni otros artefactos generados. No leer, copiar, modificar, incorporar a Git ni publicar respaldos, `.env` o secretos. Usar archivos fuente, configuración versionada y manifiestos de dependencias.

## 4. Arquitectura y responsabilidades obligatorias

Mantener **monolito modular con principios hexagonales (puertos y adaptadores)** y una separación clara entre presentación, aplicación, dominio y persistencia:

- **Controllers:** HTTP, DTOs, autenticación/autorización y traducción de errores. No implementan reglas de colección, SQL ni procesamiento de medios.
- **Services / casos de uso:** coordinan reglas de aplicación, transacciones, reintentos y contratos de puertos. No dependen directamente de FastAPI ni escriben SQL ad hoc.
- **Domain:** invariantes y modelos puros; no importar SQLAlchemy, FastAPI, PyMongo, GridFS u otra infraestructura.
- **Ports:** protocolos que necesitan servicios, independientes de implementaciones concretas.
- **Adapters:** repositorios SQL, MongoDB, imágenes o proveedor de identidad. No construyen respuestas HTTP ni realizan commits arbitrarios si la transacción pertenece al caso de uso.
- **Database:** conexiones, engines, base declarativa y ciclo de vida compartidos. No duplicar conexiones en los módulos.
- **Shared:** funciones realmente transversales (errores, sesión, seguridad, observabilidad, etc.); no colocar reglas exclusivas de colección en `shared/`.
- **Frontend:** `screens` componen, `components` renderizan, `hooks` coordinan estados, `services` realizan red, `types` definen contratos. Reutilizar cliente HTTP y mecanismos reales de sesión.

Límites de módulos: **Identidad** autentica y determina el jugador; **Catálogo** define cartas y habilidades; **Colección** gestiona la propiedad y cantidad de copias; **economía/cubos** se asigna al módulo que resulte de la auditoría de código, no se inventa a priori. No guardar la propiedad de un jugador dentro de `catalog_cards` ni duplicar definiciones e imágenes por propietario.

El flujo de entrega inicial debe quedar independiente del proveedor Google para ser invocable también desde mecanismos autorizados de prueba.

## 5. Reglas de persistencia, migraciones y operación

- PostgreSQL 16 sigue siendo la fuente de verdad de datos relacionales/transaccionales; MongoDB 7 se utiliza para GridFS y proyecciones derivadas cuando el caso lo requiera.
- En Crear Carta se reportaron las tablas `catalog_cards`, `catalog_abilities`, `catalog_card_images`, `catalog_card_code_counters`, `shared_idempotency_records`, `shared_outbox`, `identity_users` e `identity_sessions`. **Verificar definiciones y estado antes de reutilizarlas**.
- El informe de Crear Carta indica imágenes en **GridFS** (`card_assets.files`, `card_assets.chunks`), metadatos SQL y proyección MongoDB **`cards_projection`**, mantenida por eventos **`CardCreated`**. El manual de estructura antiguo describe `./uploads/cartas/`, tablas `cartas`/`outbox`, colección `cards_catalog` y Motor: **son afirmaciones potencialmente desactualizadas, no decisiones vigentes que deban imponerse al código**.
- Reutilizar SQLAlchemy Async, Alembic y las conexiones existentes. Comprobar el controlador MongoDB real en `backend/pyproject.toml` y el código; no incorporar Motor o PyMongo Async por inferencia documental.
- Conservar IDs/foreign keys y convenciones reales. En el historial de Crear Carta se usaron identificadores `VARCHAR(36)`; no asumir tipo de ID en las nuevas tablas sin verificar la migración 012.
- En Catálogo, tipos canónicos `FUE`, `AGU`, `PLA`, `ELE`, `PSI`, `LUC`; rarezas `COMUN`, `POCO_COMUN`, `RARA`, `LEGENDARIA`. No alterar reglas de Crear Carta para entregar colecciones.
- No modificar colecciones MongoDB ni introducir proyecciones de inventario por anticipación. La entrega inicial debería evaluarse como operación SQL atómica; elegir componentes definitivos tras auditoría.
- Prohibido ejecutar migraciones, `create_all()`, `stamp`, DDL/DML, `autogenerate`, downgrade o cambios de permisos sobre cualquier base en esta fase.
- No ejecutar `docker compose down -v`, borrar/recrear volúmenes, reiniciar contadores, modificar seeds, limpiar archivos GridFS ni utilizar credenciales de producción por conveniencia.
- No imprimir valores sensibles de `.env`, archivos de respaldo, credenciales OAuth, tokens ni datos personales en informes o logs.

## 6. US 3.1.1 — Recibir colección inicial: requisitos a auditar

La historia requiere, para un **jugador nuevo**:

1. Recibir **15 cartas distintas de rareza `COMUN`** que ya existan en Catálogo, seleccionadas **aleatoriamente en el servidor**.
2. Recibir **1.000 cubos** junto con esas cartas; registrar la entrega de cubos como **primer movimiento** de su historial.
3. Quedar en condiciones de construir un deck de **12 cartas distintas** (sin crearlo automáticamente).
4. Si hay **menos de 15 cartas comunes**, crear/conservar la cuenta **sin otorgar cartas ni cubos**, informar que el juego todavía no está disponible y reintentar la entrega en un ingreso posterior.
5. Asegurar **atomicidad**: ningún fallo puede dejar cartas sin cubos, cubos sin cartas o una entrega parcial.
6. Asegurar **entrega exactamente una vez**, incluso con dos primeros ingresos concurrentes o reintentos; accesos posteriores no repiten beneficios.
7. Impedir que campos o sugerencias del cliente controlen el sorteo de cartas.

**Dependencias funcionales:** US 1.1.1 (identidad de jugador/proveedor), US 1.1.3 (identidad no productiva, si existe), US 2.1.1 (catálogo elegible); habilita US 3.1.2 (consultar propiedad y cantidades) y US 3.1.3 (decks). No implementar todavía búsquedas paginadas, decks, recompensas, flujo Google nuevo ni pantallas completas de colección.

### Lo que debe descubrirse antes de diseñar tablas

- Qué define la migración `012_player_profiles_and_inventory.py`: perfiles, FK a identidad, inventario, saldos, movimientos, restricciones, índices y estados. **No suponer que implementa toda la historia.**
- Modelos/puertos/repositorios actuales de `jugadores/coleccion_mazos/`, `perfil_cuentas/` y del módulo de Identidad; determinar si están vacíos o solo parcialmente implementados.
- Qué mecanismo de sesión y perfil de jugador proporciona Google y qué ocurre en un primer login con catálogo insuficiente.
- Dónde registrar y consultar cantidad de cartas por jugador, movimientos de cubos y una marca durable de entrega. Investigar si ya existen estructuras de estos conceptos; **no proponer nombres de tablas como definitivos**.
- Qué garantías reales de locking, unicidad, idempotencia y límites de transacción existen para soportar dos inicios simultáneos.
- Cuáles son las reglas efectivas para considerar una carta común **elegible**; no inventar filtros adicionales si los requisitos oficiales no los definen.

## 7. Auditoría inicial y remediación de CI-1

El procedimiento siguiente corresponde al diagnóstico de solo lectura de CI-1 ya entregado. En CI-2, validar la migración y la provisión con motores desechables. Para el PostgreSQL aislado de loopback `15433`, presentar el SQL de privilegios antes de ejecutarlo. Mantener `cube_transactions` con lectura e inserción para el rol de aplicación. Conservar el PostgreSQL original `5432` y el MongoDB original `27017` fuera de las pruebas y de cualquier cambio.

### Procedimiento

1. Leer este contrato y comprobar `git status`, rama actual, `git log`, `git ls-files` y rutas del árbol fuente **sin cambiar el checkout ni descargar referencias**.
2. Correlacionar el manual `ESTRUCTURA-REPOSITORIO.md` con archivos rastreados, imports y tests; identificar apartados obsoletos, especialmente rutas con guiones frente a `snake_case`, almacenamiento de imágenes y bases/colecciones.
3. Inspeccionar flujo Google en `identidad_module.py`, `gestion_sesiones/`, controles de seguridad, configuración y `test_identity_google_login.py`; comprobar que la rama auditada contiene realmente la implementación del compañero.
4. Revisar historial y DAG Alembic, `012_player_profiles_and_inventory.py`, modelos SQL, repositorios y contratos de identidad/jugador/catalogo. Identificar el estado aplicado **solo si hay evidencia ya disponible sin conexión/escritura no autorizada**.
5. Verificar qué objetos de persistencia podrían representar las 15 cartas, 1.000 cubos, historial y finalización de entrega; establecer huecos sin adelantarse a crear estructuras.
6. Revisar mecanismos existentes de transacciones, bloqueos, unicidad y tolerancia a fallos; relacionar cada criterio de US 3.1.1 con evidencia concreta.
7. Entregar el informe definido en §9 **en el chat** y detenerse.

### Permitido durante el diagnóstico inicial

Inspección local de archivos, documentación, tests existentes y resultados históricos; `git status`, `git log`, `git show`, `git diff`, `git branch`, `git ls-files`, búsquedas estáticas, lectura de código/migraciones y revisión de configuración sin imprimir secretos.

### Prohibido durante el diagnóstico inicial

Editar archivos; crear migraciones, tablas, clases o documentación; cambiar ramas; `git checkout`, `switch`, `pull`, `fetch`, `merge`, `rebase`, `reset`, commit/push; ejecutar tests con efectos de escritura no aislados; iniciar contenedores para mutar datos; conectarse a bases sin autorización específica; ejecutar acciones destructivas o modificar credenciales/permisos.

## 8. Estándares para implementaciones posteriores (solo cuando se autoricen)

1. **Clean Code, SOLID, DRY y simplicidad:** responsabilidad única, código tipado, módulos cohesionados, sin capas, helpers o dependencias de relleno.
2. Antes de crear archivo, tabla, servicio, nuevo endpoint o abstracción, comprobar si existe uno equivalente y justificar la diferencia.
3. Seguir nombres de rutas **verificadas en la rama**, convenciones `snake_case`/`PascalCase` y contratos SQL reales. No renombrar módulos por estilo sin autorización.
4. Documentar módulos nuevos y contratos públicos; comentarios para invariantes, concurrencia y decisiones no evidentes. No documentar algo como probado si no lo fue.
5. Componer dependencias fuera del dominio; persistencia técnica tras puertos, transacciones explícitas y ningún commit escondido en adaptadores.
6. Probar camino feliz, catálogo insuficiente, reintento, errores parciales, concurrencia, rollback, propiedad, saldo e historial con PostgreSQL **real aislado** cuando corresponda. Distinguir tests aprobados, omitidos, simulados y no ejecutados.
7. Migraciones Alembic nuevas únicamente tras revisar revision graph, esquema de origen y compatibilidad con datos; ejecutar upgrade/downgrade solo en destinos expresamente autorizados.
8. Actualizar README, contratos, tests y ADR cuando el cambio efectivo lo justifique; nunca sobrescribir contratos del compañero sin revisión.
9. Mantener secretos fuera de Git, roles mínimos y entornos de prueba controlados; no habilitar identidades de prueba en producción.
10. Antes de cada commit, reportar archivos, diff, pruebas, riesgos y decisiones. **No realizar commit/push automáticamente**; no avanzar de etapa sin permiso.

## 9. Informe obligatorio de la auditoría US 3.1.1

Entregar con **rutas, funciones, clases, constraints y revisiones verificadas**, no solo una descripción conceptual:

1. **Rama y Git:** qué commit está abierto, dónde están Crear Carta y Google, y si existe merge/integración comprobable.
2. **Discrepancias documentales:** rutas reales, diferencias con `ESTRUCTURA-REPOSITORIO.md`, `AGENTS.md` anterior y snapshot entregado.
3. **Login Google:** endpoints, validación del proveedor, persistencia de identidad, sesión de aplicación, roles, concurrencia y pruebas; puntos no comprobados.
4. **Inventario SQL/Alembic:** estructura y contenido de 012, dependencia entre migraciones, cabezas, modelos ORM e indicios del estado aplicado. Distinguir esquema declarado y real.
5. **Catálogo y jugadores:** archivos de lectura de cartas elegibles, modelos de perfil, inventario, saldo, movimientos y entrega inicial (presentes o ausentes).
6. **Transacciones y mecanismos reutilizables:** sesiones, UoW, locks, restricciones únicas, idempotencia, errores y separación de responsabilidades.
7. **Matriz de cobertura US 3.1.1:** requisito → componente/archivo → estado de evidencia → brecha/riesgo.
8. **Impacto en US 3.1.2 y 3.1.3:** qué debería poder consumirse después, sin diseñar o implementar esas historias ahora.
9. **Preguntas para el equipo y decisiones pendientes:** alternativas claras, sin declarar nuevas tablas o migraciones como ya aprobadas.

**Formato:** informe en el chat. Ninguna escritura, modificación o ejecución de implementación. Detenerse al terminar.

---

**Punto de revisión:** entregar el dictamen CI-5E y detenerse. El backend queda disponible para una integración React autorizada por separado, según el contrato HTTP y los límites del informe de cierre.
