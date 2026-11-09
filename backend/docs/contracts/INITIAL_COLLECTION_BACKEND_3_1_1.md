# Poké-Arena — Contrato de implementación del backend

**Historia:** US 3.1.1 — Recibir colección inicial  
**Ámbito:** backend exclusivamente · Monolito modular hexagonal  
**Fecha:** 2026-11-09  
**Rama de referencia auditada:** `feature/coleccion-inicial` (verificar HEAD antes de trabajar)  
**Estado:** contrato propuesto para revisión y ejecución por etapas; **no representa implementación realizada**.

## 1. Objetivo y autoridad

Implementar la entrega inicial para jugadores autenticados por Google sin reescribir el sistema de identidad ni Crear Carta. El servicio debe conceder **15 cartas distintas `COMUN`, elegidas aleatoriamente por el servidor entre cartas con imagen `READY`, y 1.000 cubos**, una sola vez por jugador y de modo atómico. Los cubos constituyen el **primer movimiento** de su historial.

**Orden de autoridad ante discrepancias:** requerimientos oficiales de la US y decisiones explícitas del usuario en esta conversación; `AGENTS.md` vigente; estructura verificada en el árbol y migraciones; contratos existentes; código real. Registrar contradicciones, no resolverlas silenciosamente. Antes de editar, leer `AGENTS.md`, `ESTRUCTURA-REPOSITORIO.md`, los contratos de Identidad y Crear Carta, las migraciones 005/006/010/011/012 y los archivos mencionados en la auditoría de US 3.1.1.

### 1.1. Requisitos oficiales no negociables

- Primer ingreso con catálogo suficiente: entrega automática de 15 cartas **distintas** de rareza `COMUN`, seleccionadas aleatoriamente en el servidor, y 1.000 cubos.
- Debe posibilitar la posterior creación de un deck válido de 12 cartas diferentes; **no crear el deck** en esta historia.
- Entrega **todo o nada**: nunca dejar cartas, cubos, movimiento o marca parcialmente confirmados.
- Menos de 15 elegibles: identidad y sesión pueden crearse, pero **no** se entregan cartas ni cubos. Informar indisponibilidad; reintentar en un ingreso posterior.
- Dos primeros ingresos concurrentes: una única entrega; reingresos posteriores no duplican premios.
- Los 1.000 cubos deben figurar como **primer movimiento** del historial.
- Ningún dato controlado por el cliente influye en el sorteo.

### 1.2. Decisiones de diseño aprobadas por el usuario

1. Una carta solo es elegible si `catalog_cards.rarity = 'COMUN'` **y** su imagen asociada está en estado `READY` en `catalog_card_images`. Requerir relación y referencias de original/miniatura consistentes con el contrato existente. No leer ni procesar archivos binarios en la transacción de entrega, a menos que una auditoría pruebe que es indispensable.
2. Flujo del jugador: **login inicial → presentación/apertura del paquete inicial → funcionalidades de jugador habilitadas**. Hasta finalizar la apertura, el backend deniega acciones de juego, colección avanzada y economía. Identidad, perfil mínimo, consulta del paquete y cierre de sesión siguen accesibles.
3. El rol `PLATFORM_ADMIN` **no juega**, no obtiene colección inicial y no tiene acceso a endpoints exclusivos del jugador. No usar `requerir_jugador` sin verificar su semántica actual, pues admite ambos roles.
4. Corregir hallazgos críticos de seguridad o arranque mediante cambios pequeños y comprobados. No rediseñar funcionalidades estables para resolver riesgos accesorios.
5. Codex trabaja **solo en backend**. No editar `frontend/`, ni implementar pantallas, animaciones o hooks React.

## 2. Resolución explícita de entrega automática versus apertura

**Dos hechos distintos:** (A) *beneficios provisionados*, y (B) *paquete abierto/desbloqueo confirmado*. No deben confluir.

- **A — Provisión automática:** después del login Google válido y de confirmar la identidad/sesión, el caso de uso intenta entregar los beneficios en una **transacción SQL independiente**. Si hay suficientes cartas, guarda inventario, saldo, primer movimiento y `has_received_initial_collection=true`. Si no hay, deja `false` y beneficios intactos.
- **B — Apertura del paquete:** la interfaz futura mostrará el paquete y, al finalizar la interacción, enviará una petición autenticada para **confirmar la apertura**. Solo entonces se desbloquean las demás funcionalidades de jugador. En el backend la confirmación debe ser idempotente.
- La cuenta puede tener beneficios ya provisionados y una apertura aún pendiente. Un nuevo login **no vuelve a premiar** y conserva el bloqueo hasta confirmar la apertura; después de una apertura completada, los futuros logins permiten acceso normal. Esta distinción es esencial para cumplir simultáneamente el criterio oficial de entrega al primer ingreso y la nueva regla de onboarding.
- **Cambio mínimo justificado de esquema:** la 012 solo representa la provisión. Para persistir la apertura, proponer una **migración sucesora nueva** (sin modificar la 012) que añada a `player_profiles` una columna nullable `initial_pack_opened_at TIMESTAMPTZ` (o equivalente validado). `NULL` significa no abierto. No agregar otra tabla ni simular apertura con `has_received_initial_collection`.
- **No es posible verificar técnicamente que la persona vio la animación**: el servidor puede exigir una confirmación autenticada, no una experiencia visual. Una futura UI debe invocarla después de la apertura. No inventar frontend para fingir que el flujo visual está terminado.
- Antes de implementar la migración, comprobar si existe ya una marca equivalente en la rama vigente; reutilizarla si es semánticamente correcta.

## 3. Persistencia: reutilizar antes de crear

Migración `012_player_profiles_and_inventory.py` (declarada en código; **su aplicación a una base real no está verificada**):

| Tabla | Columnas relevantes | Uso |
|---|---|---|
| `player_profiles` | `user_id` PK/FK, `elo`, `cubes`, `has_received_initial_collection`, timestamps | Saldo, marca de beneficios, bloqueo por jugador; apertura (solo con migración sucesora) |
| `player_cards` | PK (`user_id`, `card_id`), `quantity`, `acquired_at` | 15 referencias únicas a `catalog_cards`, cantidad inicial 1 |
| `cube_transactions` | `id`, `user_id`, `amount`, `balance_after`, `reason`, `created_at` | Primer movimiento `+1000`, saldo posterior 1000 |
| `catalog_cards` + `catalog_card_images` | `id`, `rarity`, relación de imagen y estado `READY` | Selección de cartas elegibles |
| `identity_users` + `identity_sessions` | Identidad Google estable `(provider, provider_subject)` y sesión propia | Usuario autenticado |

**No** crear tablas alternativas de cartas, perfiles, inventario, movimientos ni entidades paralelas en MongoDB. Mantener los IDs `VARCHAR(36)` y las FKs ya definidas. No usar Outbox, GridFS ni `cards_projection` como autoridad de la selección o del inventario.

### 3.1. Invariantes de integridad

- `has_received_initial_collection=true` implica que la entrega transaccional de 15 cartas distintas y el abono de 1.000 se completó; el caso de uso no debe marcarla anticipadamente.
- `initial_pack_opened_at IS NOT NULL` implica `has_received_initial_collection=true` (reforzar con `CHECK` SQL si es compatible y no rompe filas históricas).
- La entrega inicial se permite únicamente desde un perfil **no premiado, sin inventario preexistente, `cubes=0` y sin movimientos previos de cubos**; de lo contrario, reportar inconsistencia explícita para investigación. No sobrescribir balances ni borrar datos.
- Todas las escrituras de la entrega se confirman en una transacción; antes de la entrega, ningún otro caso de uso de economía del jugador puede registrar movimientos.
- La PK compuesta de `player_cards` protege la unicidad de inventario, **pero no sustituye** el bloqueo y la marca que evitan un segundo abono.
- `cube_transactions` se trata como ledger append-only en los servicios: no actualizar ni eliminar movimientos. Auditar permisos reales y considerar endurecimiento mínimo de privilegios; no romper mantenimiento existente sin evidencia.
- El primer movimiento se persiste con `reason='INITIAL_COLLECTION'`, definido en el dominio. La entrega registra exactamente un movimiento de 1.000 cubos.
- Para cuentas históricas con `has_received_initial_collection=true`, definir y probar política de migración de apertura: conservar `opened_at=NULL` para exigir revelado, **sin entregar premios nuevos**. No completar aperturas históricas por defecto sin aprobación.

## 4. Arquitectura y archivos

### 4.1. Reutilización existente, sujeta a comprobación de HEAD

- `backend/src/modules/identidad/identidad_module.py`
- `backend/src/modules/identidad/gestion_sesiones/{controllers/sesiones_controller.py,services/sesiones_service.py,adapters/sql_sesiones.py,adapters/google_oidc.py,ports/sesiones_ports.py}`
- `backend/src/database/postgresql/connection.py` (`AsyncSessionLocal`, `transactional_session()`)
- `backend/src/modules/catalogo/gestion_cartas/adapters/{cartas_orm.py,sql_carta_repository.py}`
- `backend/src/modules/catalogo/catalogo_module.py`
- `backend/alembic/versions/012_player_profiles_and_inventory.py`
- `backend/tests/test_identity_google_login.py`

Conservar los imports y nombres **reales** con guiones bajos: `gestion_cartas`, `gestion_sesiones`. No renombrar carpetas ni duplicar composición. Google y la generación de Bearer opaco permanecen en Identidad. No añadir SQL de inventario a `google_oidc.py`.

### 4.2. Paquete propuesto (solo si los componentes no existen)

```text
backend/src/modules/jugadores/coleccion_mazos/
├── domain/entrega_inicial_model.py
├── ports/entrega_inicial_ports.py
├── services/entrega_inicial_service.py
└── adapters/sql_entrega_inicial.py
```

Separar dominio puro, puertos tipados (`Protocol`), orquestación sin SQL/FastAPI y adaptador SQL. No fragmentar una implementación cohesionada en repositorios abstractos sin consumidores reales. Definir composición una sola vez en el módulo existente de jugadores o el punto compartido que se encuentre; registrar dependencias sin acoplamientos circulares.

- **Servicios:** reglas, estados y coordinación de la unidad de trabajo. No hacer `commit()` desde adaptadores de bajo nivel.
- **Adaptador SQL:** una única sesión/transacción, bloqueo y escrituras atómicas.
- **Controlador de onboarding:** autenticación y validación HTTP, sin reglas de sorteo ni SQL directo.
- **Identidad:** orquestar la provisión *después* de obtener usuario y sesión, mediante una interfaz/callback inyectada en composición. Ambas rutas de Google actuales deben invocar el mismo punto común. No condicionar provisión a `is_new_user` (no es seguro frente a concurrencia y no soporta reintentos).

## 5. Caso de uso de provisión automática

Precondición: Google OIDC validado; usuario y perfil confirmados; rol efectivo `PLAYER` verificado en servidor. `PLATFORM_ADMIN` omite totalmente el caso de uso.

Algoritmo lógico:

```text
POST Google login existente (sin duplicar rutas)
  -> verificar Google y crear/recuperar identidad + sesión (transacción actual)
  -> si rol efectivo == PLAYER: asegurar_coleccion_inicial(user_id)
       BEGIN
         SELECT player_profiles WHERE user_id = :id FOR UPDATE
         perfil ausente => error de integridad; no inventar perfil fantasma
         marca true => ALREADY_GRANTED, sin escrituras
         validar cubos=0, player_cards vacío e historial vacío
         seleccionar 15 catalog_cards distintos con rarity=COMUN
             JOIN imagen y status=READY, referencias originales y miniatura válidas
             ORDER BY random() LIMIT 15
         menos de 15 => INSUFFICIENT_CATALOG, sin beneficios
         INSERT 15 player_cards (quantity=1)
         INSERT 1 cube_transactions (+1000, balance_after=1000)
         UPDATE player_profiles SET cubes=1000,
             has_received_initial_collection=true, updated_at=...
       COMMIT; rollback total si cualquier escritura falla
  -> entregar sesión y estado consultable del onboarding
```

La identidad/sesión y la entrega pueden utilizar dos transacciones; la **atomicidad del premio** se limita a inventario+saldo+ledger+marca, porque la cuenta debe sobrevivir a catálogo insuficiente o fallo de entrega. Documentar respuesta de error y reintento del login de manera coherente: no devolver silenciosamente un éxito de provisión si falló. No usar `Idempotency-Key` por operación HTTP: la identidad del jugador, el bloqueo y la marca durable constituyen la idempotencia de negocio.

`ORDER BY random()` es aceptable inicialmente para el tamaño esperado (~10.000 cartas), sujeto a evaluación de plan si crece. Seleccionar en PostgreSQL, **no** desde una proyección MongoDB ni desde una respuesta que pueda contener seeds sintéticas sin FK SQL.

## 6. Apertura, autorización y contrato HTTP (backend solamente)

El backend ofrece las siguientes rutas. La sección 15 especifica el contrato HTTP implementado:

| Operación | Ruta | Autorización |
|---|---|---|
| Consultar onboarding | `GET /api/v1/player/initial-pack` | Bearer válido, rol efectivo exactamente `PLAYER` |
| Confirmar apertura | `POST /api/v1/player/initial-pack/open` | Bearer válido, rol efectivo exactamente `PLAYER` |

`GET` no entrega ni modifica saldo: solo informa el estado actual. La provisión ocurre desde el login; nunca debe depender de que el navegador invoque `GET`.

**Estados de lectura:**
- `PENDING_CATALOG`: `has_received=false` y catálogo insuficiente; mensaje de juego temporalmente no disponible. Solo un login posterior reintenta automáticamente la entrega, salvo decisión explícita de habilitar otra reentrada.
- `READY_TO_OPEN`: `has_received=true`, `opened_at=NULL`; devolver los 15 IDs/códigos de cartas para la futura revelación, consultados de `player_cards` (únicos y disponibles porque aún está bloqueado el resto del juego).
- `COMPLETED`: `has_received=true`, `opened_at != NULL`; funcionalidades del jugador desbloqueadas.
- Una inconsistencia entre marca, inventario, saldo e historial **no** se presenta como `READY_TO_OPEN`: error de integridad y diagnóstico sin datos sensibles.

**`POST /open`:** no acepta `user_id`, listado de cartas, cantidades, saldo ni información para sortear; el servidor deriva `user_id` de `Principal`. Bloquear perfil, exigir que `has_received=true`, actualizar `opened_at` solo si está vacío y devolver `COMPLETED`. Repetición de la misma llamada devuelve el estado completado sin escribir otra vez. Si la colección sigue pendiente, responder error de conflicto/indisponibilidad con Problem Details; jamás hacer la entrega desde `POST /open` como sustituto de la provisión automática.

**Guard de funcionalidades:** incorporar/verificar una dependencia compartida *de uso específico en endpoints de jugador* que exija rol efectivo `PLAYER`, `has_received=true` y `opened_at != NULL`. Aplicarla a las rutas ya existentes que permitan jugar, usar economía, crear decks o consultar funcionalidades completas; no bloquear login, logout, perfil mínimo, estado/apertura del paquete ni healthchecks. **No** aplicar indiscriminadamente middleware global ni cambiar `requerir_jugador` sin evaluar quién lo usa. Toda futura ruta restringida de jugador deberá reutilizar el guard. React solo deberá consumirlo en etapa frontend, fuera del alcance de Codex.

Cualquier modificación de DTO de login debe ser aditiva y compatible con clientes existentes. Preferir endpoint de estado independiente si evita romper contratos existentes. No afirmar que el frontend ya muestra/abre un paquete: eso queda pendiente.

## 7. Seguridad y hallazgos de auditoría

Verificar **antes** de implementar la lógica dependiente:

1. **Cadena de imports:** `mongo_carta_repository.py` importa `motor.motor_asyncio`, mientras Motor no figura en `pyproject.toml`. Reproducir arranque limpio; eliminar import obsoleto o adaptar mínimamente a `pymongo.AsyncMongoClient` si está justificado. No agregar Motor ni rediseñar todo MongoDB por inercia.
2. **Migración 012:** verificar grafo Alembic y revisión aplicada en PostgreSQL **aislado**; comprobar privilegios y restricciones reales, sin tocar `pokearena_db` ni esquemas compartidos.
3. **`is_new_user`:** nunca usarlo como criterio para otorgar o desbloquear; reutilizar marca persistente bajo bloqueo.
4. **Perfil fantasma:** el `LEFT JOIN` de `/identity/me` presenta `0/0/false` si falta perfil. El servicio de entrega debe fallar de forma controlada ante ausencia real; mejorar el contrato de perfil solo si es seguro y acotado.
5. **Ledger:** auditar permisos `UPDATE/DELETE` de `cube_transactions` y la inmutabilidad de hechos económicos. Documentar brecha y corregir con mínimo impacto cuando esté permitido; evitar migraciones que rompan flujos históricos.
6. **Privilegios Google:** la allowlist por correo no verifica `email_verified`. Considerar esta **brecha crítica de escalamiento a `PLATFORM_ADMIN`**; corregir el chequeo de claim en la ruta de elevación del correo si los cambios son acotados, y añadir prueba de regresión. La comparación basada en `sub` puede conservar su semántica si es segura. No cambiar la política de roles sin aprobación.
7. **Bloqueo por usuario:** probar dos sesiones concurrentes en PostgreSQL real y que se produzca un solo abono/ledger; no confiar únicamente en mocks.

Si alguna corrección requiere cambios sustanciales, detener esa intervención y documentar la causa, alternativa y autorización necesaria. No dejar vulnerabilidades críticas conocidas habilitadas por comodidad.

## 8. Datos de prueba: 80 cartas con una única imagen fuente

Codex debe crear un **script de seed para desarrollo/pruebas**, no un seed automático en el arranque, con estas propiedades:

- La única imagen fuente es `<raíz>/prueba/ip.png`. El script exige que exista y aplica el procesador de Crear Carta. El límite es de 1 a 5.000.000 bytes, mínimo 600×840, proporción exacta 5:7, máximo 20 Mpx y un fotograma.
- Generar **80 cartas**, exactamente 20 de cada rareza `COMUN`, `POCO_COMUN`, `RARA` y `LEGENDARIA`. Los nombres temáticos son únicos y reproducibles con `--seed`. `cost` va de 0 a 10 y `power` de -20 a 20. Los tipos se distribuyen entre FUE/AGU/PLA/ELE/PSI/LUC.
- Asociar la habilidad existente `HAB-000` y reutilizar el archivo fuente para las 80 peticiones. Crear Carta controla sus originales y miniaturas GridFS, incluidas las referencias y la limpieza de fallos.
- Invocar el **mismo caso de uso/API autenticada de Crear Carta** (contrato `POST /api/v1/content/cards`, multipart, Bearer administrador, `Idempotency-Key`) o su servicio de aplicación, según lo más fiable en la instalación local. **Prohibidos INSERT directos** en `catalog_cards`, escrituras manuales a GridFS, bypass de validaciones, asignación manual de códigos, cambios a counters o llamadas aisladas a Outbox.
- Reejecución segura: identificar registros propios por prefijo de nombre como `CI-SEED-`, seed estable e idempotencia por carta; no crear duplicados si un intento anterior confirmó parte. Reportar registros existentes, nuevos y fallidos. No borrar ni reescribir cartas existentes para reiniciar el script.
- **Protección fuerte del entorno:** `--dry-run` por defecto. Escritura solo con `--apply`, confirmación explícita, base PostgreSQL aislada con nombre permitido (`pokearena_alembic_*`) y MongoDB de prueba igualmente identificado, ambos en loopback. Abort si se detecta base original, producción, credenciales no correspondientes o destinos ambiguos. No inferir permisos por el nombre del archivo `.env`.
- Al terminar, verificar en la misma instancia que se crearon cartas `COMUN` con imágenes `READY`, que existen referencias a original y miniatura, y que se pueden listar al menos 15 elegibles por la consulta real de colección. No ejecutar una entrega de prueba contra un usuario existente sin autorización.
- Preferir la carpeta de herramientas ya utilizada por el repositorio para ubicar el script; no inventar `backend/scripts/` ni modificar `manage.py` sin evaluar primero sus comandos existentes. Incluir instrucciones de uso reproducibles y **sin secretos**.
- No agregar la imagen fuente ni archivos de salida al control de versiones sin revisión del diff. No iniciar seed al arrancar FastAPI o Docker.

Cada carta se confirma en su propia transacción. El lote se puede reanudar con el mismo actor, semilla e imagen. La ejecución persistente requiere autorización separada, dry-run y respaldos legibles.

## 9. Pruebas y criterios de aceptación

**Base aislada PostgreSQL 16 con revisión 012 y sucesora de apertura; MongoDB 7 aislado solo para el seed y pruebas necesarias de Crear Carta.** No ejecutar tests que limpian tablas sobre una base compartida. Probar de verdad restricciones, concurrencia y transacciones; mocks como complemento, nunca como única evidencia.

1. Login Google de `PLAYER`, 15 o más cartas `COMUN` `READY`: 15 `card_id` distintos, quantity 1, saldo +1000, primer ledger +1000, `has_received=true`, `opened_at=NULL`, jugador bloqueado para juego.
2. Mínimo exacto 15: entrega válida. Menos de 15 elegibles (aunque haya otras cartas comunes con imagen no READY): perfil creado, 0 cartas, 0 cubos, 0 ledger, marca false; mensaje de indisponibilidad.
3. Reingreso después de catálogo insuficiente: cuando existan 15 elegibles, se provisiona una vez.
4. Dos logins concurrentes del mismo Google `sub`: una identidad, un perfil, una entrega, un primer movimiento; ninguna excepción SQL no controlada.
5. Fallo simulado después de la N.ª inserción o del ledger: rollback total de beneficios y marca; reintento en siguiente login entrega completo.
6. `POST /open` antes de provisión: bloqueado; una vez provisionado: primera confirmación habilita el juego y las siguientes son idempotentes.
7. Antes de abrir: rutas de jugador protegidas responden 403/estado HTTP acordado, pero autenticación, `/identity/me`, consulta de paquete y logout funcionan. Después de abrir: acceso autorizado a las rutas disponibles.
8. `PLATFORM_ADMIN` Google y administrador `LOCAL`: jamás se les entregan 15 cartas ni cubos y no pueden llamar endpoints exclusivos de jugador.
9. Cliente no puede proporcionar IDs de cartas para influir en selección, `user_id` distinto del principal ni balance/flags arbitrarios.
10. Primer movimiento del ledger de un perfil nuevo es el abono inicial. Perfil con movimientos previos o inventario anómalo no se repara automáticamente ni se premia dos veces.
11. Contratos existentes de Crear Carta, login, búsqueda y Outbox no sufren regresiones; verificación de arranque limpio de FastAPI.
12. Seed: modo seco sin escrituras, lote de 80 cartas autorizadas con 20 por rareza, reejecución sin duplicados, imágenes `READY`, GridFS y proyección de Outbox.
13. Revisar pruebas omitidas por ausencia de motores; nunca presentar skips como aprobadas. Ruff, Mypy y compilación Python dentro del alcance configurado; controles negativos cuando aporten valor.

## 10. Etapas autorizables, entregables y controles

**Etapa CI-1 — Contrato + verificación del entorno (solo lectura / pruebas seguras):** verificar estructura/HEAD, historial Alembic, disponibilidad de 012 en base aislada, permisos, capacidad de arrancar FastAPI. Identificar y corregir únicamente bloqueos críticos **tras autorizarlos por separado**. Entregable: diagnóstico y plan de archivos. No escribir aún nueva migración/servicio.

**Etapa CI-2 — Persistencia y servicio:** propuesta y revisión de migración sucesora de apertura; implementar unidad transaccional, dominio, puertos y repositorio mínimos; pruebas de atomicidad, elegibilidad y concurrencia. No tocar el frontend.

**Etapa CI-3 — Integración de login, API y guards:** conectar las dos rutas Google al mismo flujo sin alterar seguridad OIDC, exponer estado y apertura, exigir PLAYER exacto, aplicar gate a los endpoints de jugador existentes o dejar explícitamente cuáles todavía no existen.

**Etapa CI-4 — Lote de 80 cartas + integración real:** reutilizar Crear Carta, presentar el dry-run y validar el flujo en motores desechables. Aplicar en motores persistentes solo con autorización posterior.

**Etapa CI-5 — Auditoría final:** regresiones, revisión de diffs, documentación y dictamen de cierre; **sin commit ni push automáticos**.

**Regla de avance:** terminar y reportar cada etapa. No ejecutar la siguiente sin instrucción del usuario. Nunca modificar `pokearena_db`, borrar volúmenes, ejecutar `down -v`, `stamp`, `create_all`, migraciones automáticas sobre bases compartidas, ni almacenar secretos en Git. Migraciones nuevas se prueban `upgrade/downgrade` en copias aisladas; los históricos no se editan. Todos los cambios deberán incluir tipos, docstrings de módulos/funciones públicas, comentarios sobre concurrencia y seguridad, Clean Code/SOLID/DRY y pruebas reales.

## 11. Documentación del repositorio: cambios necesarios

1. **Agregar** `backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md` (este contrato). Es la guía única de la US para Codex.
2. **Actualizar `AGENTS.md`** para que deje de autorizar exclusivamente la auditoría de solo lectura y señale **CI-1** como etapa activa; enlazar este contrato. Conservar el procedimiento de autorización por etapa y las reglas generales; nunca reemplazar todo `AGENTS.md` por un prompt corto.
3. **Actualizar `ESTRUCTURA-REPOSITORIO.md` solo cuando se creen los archivos efectivos**. Corregir allí las descripciones antiguas de Motor, imágenes en disco, `outbox` y `cards_catalog` si aún aparecen; usar `pymongo.AsyncMongoClient`, GridFS `card_assets`, `shared_outbox` y `cards_projection` según la implementación verificada. No imponer estructura propuesta como si ya existiera.
4. **Actualizar README raíz** únicamente si cambian instalación, variables de entorno, ejecución de la API, nuevo endpoint o procedimiento del seed.
5. **No crear ADR o documentos duplicados por defecto**; solo una nota de decisión adicional si aparece una controversia real no cubierta por este contrato.
6. **No modificar archivos frontend**. La vista de apertura, animación y consumo del nuevo endpoint pertenecen a una fase posterior del equipo.

## 12. Evidencia y reporte obligatorio para Codex

Por cada etapa: rama/HEAD, archivos inspeccionados, archivos creados/modificados, justificación de cada cambio, comandos exactos, BD/URL sanitizadas usadas, versión Alembic antes/después, tests ejecutados/aprobados/omitidos/fallidos, resultados de concurrencia y rollback, análisis de riesgos pendientes y diff de Git sin secretos. Separar **diseño**, **implementado**, **validado en pruebas**, **aplicado en BD aislada** y **pendiente**. No atribuir a Google real una prueba hecha solo con JWKS simulado.

**Bloqueo de avance:** si algún requisito oficial colisiona con el esquema/arquitectura efectiva o impide cumplir la entrega automática y la apertura, reportarlo antes de simplificar el comportamiento; no disimular el conflicto implementando solo el flujo más fácil.

## 13. Frontera implementada en CI-2

- La revisión `013_initial_pack_opened_at` agrega una columna nullable a `player_profiles` y el check `ck_player_profiles_initial_pack_opened`. Los perfiles premiados de 012 conservan los beneficios y quedan con apertura pendiente. Después del upgrade, el aprovisionamiento concede `UPDATE(initial_pack_opened_at)` por columna si ya existe. El historial conserva lectura e inserción para la aplicación.
- `jugadores_module.crear_servicio_entrega_inicial()` compone el servicio interno. `EntregaInicial.asegurar(token_sesion)` deriva el ID de un Bearer Google vigente mediante Identidad y usa una transacción para bloquear perfil, sortear y registrar el premio. Devuelve `GRANTED`, `ALREADY_GRANTED`, `INSUFFICIENT_CATALOG` o `NOT_ELIGIBLE`. Un perfil faltante o con beneficios incompatibles y un fallo SQL producen errores de aplicación distintos. La cuenta y sesión se confirman fuera de la transacción de beneficios.
- Identidad excluye rol persistido administrativo, proveedores distintos de Google y sujetos reservados. Con allowlist de correos, exige evidencia del correo actual y excluye coincidencias aun sin evidencia, además de correos reservados verificados en sesiones anteriores de CI-1. La evidencia anterior a CI-1 que nunca se persistió no puede reconstruirse si también se reemplazó el correo o rol. Antes de habilitar el flujo HTTP, conciliar los sujetos administrativos históricos conocidos y conservar las sesiones que respaldan esa evidencia.
- La selección usa `catalog_card_images.state = 'READY'`, referencias GridFS canónicas y distintas, y miniatura WebP. La transacción solo lee metadatos SQL. Cualquier futura operación económica debe respetar el mismo bloqueo por perfil y verificar la apertura antes de escribir.
- CI-3 debe resolver cómo presentar `NOT_ELIGIBLE` y los errores de provisión al cliente, y conectar los endpoints. En CI-2 solo existe el servicio interno y la persistencia del estado de apertura.

## 14. Inmutabilidad de cuentas en CI-3A

- `identity_users.role` es el tipo permanente `PLAYER` o `PLATFORM_ADMIN`. El alta Google lo asigna una vez. Al reingresar, la política vigente se usa para autorizar la sesión y detectar discordancias. Ambas rutas de Google devuelven `409 identidad_tipo_en_conflicto` ante un tipo incompatible o un correo administrativo ambiguo. Una sesión vigente con política incompatible recibe `403` con el mismo código en las dependencias de Identidad. El formato del Bearer y del éxito se conserva.
- Una nueva sesión administrativa Google acredita su tipo de emisión con el ID de sesión, vinculado a la huella del Bearer y, cuando corresponde, al correo verificado. Los Bearer administrativos Google previos requieren reautenticación y reciben `401`. Se conserva el acceso por `sub` y por correo con `email_verified=true`. El administrador `LOCAL` mantiene su autenticación y su límite de intentos.
- Solo `PLAYER` recibe perfil de juego en el login. Un perfil técnico de administrador heredado se conserva. La regla anterior que contemplaba una promoción posterior queda sustituida por el rechazo de conversiones. CI-2 sigue excluyendo a la identidad administrativa y conserva cualquier premio existente.
- `014_identity_account_immutable` protege `id`, `provider`, `provider_subject` y `role` y restringe la escritura de los roles de aplicación. El downgrade retira el trigger y conserva los permisos restringidos. Las identidades con clasificación histórica que no se pueda justificar deben conciliarse antes de activar la entrega automática.

## 15. Integración HTTP en CI-3B

Las dos rutas Google comparten el callback de provisión después de confirmar la identidad y la sesión. La identidad administrativa omite el callback. `GRANTED`, `ALREADY_GRANTED` e `INSUFFICIENT_CATALOG` conservan los DTO de éxito y sus estados `200` o `201`. Ante un fallo, la sesión ya confirmada permanece en SQL y el error no entrega su Bearer. Una transacción de premio fallida puede reintentarse al ingresar de nuevo. Los fallos esperados devuelven `403 jugador_no_elegible`, `409 provision_inconsistente` o `503 provision_no_disponible`. Identidad conserva sus errores propios, incluido `409 identidad_tipo_en_conflicto`.

`GET /api/v1/player/initial-pack` y `POST /api/v1/player/initial-pack/open` requieren Bearer válido de `PLAYER` y devuelven `200` con `state`, `received`, `opened`, `opened_at` y `cards`. No aceptan parámetros de consulta. POST admite una petición sin cuerpo o un objeto JSON vacío.

| Estado | Contrato |
|---|---|
| `PENDING_CATALOG` | Perfil sin premio ni datos económicos. El siguiente login puede reintentar. GET no provisiona. |
| `READY_TO_OPEN` | Premio íntegro. `cards` contiene las 15 cartas asignadas con `id`, `code` y `name`. |
| `COMPLETED` | Apertura registrada. `opened_at` se conserva en reintentos y `cards` es vacío. |

La apertura usa el mismo bloqueo exclusivo por perfil que la provisión y solo actualiza `initial_pack_opened_at`. Las rutas rechazan una sesión inválida con `401`, la falta de autorización de jugador con `403`, apertura prematura con `409 paquete_pendiente` y datos inconsistentes con `409 paquete_inconsistente`. Los parámetros o campos no admitidos devuelven `422` y la indisponibilidad SQL devuelve `503 paquete_no_disponible`.

El guard `requerir_jugador_habilitado` responde `403 paquete_sin_abrir` antes de la confirmación. Actualmente no existen consumidores de juego, mazos, inventario avanzado o economía. El guard no se aplica a Catálogo compartido, login, perfil mínimo, logout o salud.

## 16. Remediación y cierre de CI-5

CI-5B.1 unificó la validación del premio cerrado para reingreso, consulta y apertura. Un reingreso con premio cerrado inconsistente devuelve `409 provision_inconsistente` sin repetir el abono ni alterar los beneficios. Después de abrir, `COMPLETED` y el acceso se basan en `initial_pack_opened_at`. La consulta y la apertura repetida conservan el estado aunque cambien el saldo o el inventario legítimamente.

CI-5C verificó ambos ingresos Google con JWT y JWKS de laboratorio. CI-5D concilió las 80 cartas de `CI4-2026` y confirmó 20 comunes elegibles. El backend queda **aprobado con observaciones** para integrar el onboarding React conforme a las rutas de la sección 15. El [informe CI-5E](CI_5_INFORME_CIERRE_BACKEND.md) recoge pruebas, observaciones operativas y alcance del frontend.
