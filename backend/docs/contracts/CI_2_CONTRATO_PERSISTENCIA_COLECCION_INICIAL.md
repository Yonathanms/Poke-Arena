# Poké-Arena — Contrato CI-2: Persistencia y servicio de colección inicial

**Historia:** US 3.1.1 — Recibir colección inicial
**Rama:** `feature/coleccion-inicial` (comprobar rama y HEAD reales antes de editar)
**Etapa autorizable:** CI-2 exclusivamente
**Referencia principal:** `backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md`
**Estado de partida:** CI-1 y su remediación reportadas como completadas; corroborar cambios y pruebas en el árbol actual.
**Alcance:** backend, persistencia SQL, dominio, puertos, adaptadores, servicio y pruebas. Sin frontend, integración de rutas/login (CI-3), seed (CI-4), commit ni push.

## 1. Mandato y precedencia

Implementar **el núcleo reutilizable y transaccional** de entrega inicial, dejando interfaces listas para integrar en CI-3, sin ejecutar la integración anticipadamente. Leer previamente `AGENTS.md`, `ESTRUCTURA-REPOSITORIO.md`, el contrato principal de US 3.1.1, contratos existentes de Identidad y Crear Carta, código vigente, `manage.py` y migraciones 010–012. No sustituir hechos verificados por supuestos. Ante conflictos, aplicar requerimientos oficiales y decisiones explícitas del usuario, registrar contradicciones y detener el cambio afectado.

**Requisitos obligatorios:** jugador Google elegible recibe una sola vez **15 cartas distintas `COMUN` con imagen `READY`**, escogidas aleatoriamente **en PostgreSQL y por el servidor**, más **1.000 cubos** como **primer movimiento** de su historial. Confirmar cartas + saldo + movimiento + marca de recepción en **una transacción SQL**. Si hay menos de 15 elegibles, no otorgar nada; cuenta y sesión pueden persistir y un login posterior podrá reintentar. Dos logins simultáneos no duplican la entrega. No crear deck, no leer binarios de imágenes para sortear, no usar MongoDB como autoridad del inventario.

## 2. Estado real conocido y comprobaciones iniciales

Según la remediación de CI-1 reportada:
- PostgreSQL de prueba: contenedor `pokearena-pg-frontend-dev`, `127.0.0.1:15433`, BD `pokearena_alembic_frontend_dev`; revisión aplicada `012_player_profiles_inventory`. Mongo aislado en `127.0.0.1:27029` si fuera necesario para regresiones; **no usar bases originales** de los puertos 5432 y 27017.
- El backend ya arranca sin Motor y utiliza PyMongo asíncrono.
- La elevación administrativa por correo requiere `email_verified` booleano `true` y evidencia asociada a la sesión. Persisten posibles Bearer históricos con rol efectivo `PLAYER`; la allowlist por `sub` conserva su semántica.
- `orm_media_test` tiene `SELECT`/`INSERT` en `player_profiles`, `player_cards`, `cube_transactions` y `UPDATE` **por columna** en `player_profiles` para `cubes`, `has_received_initial_collection`, `updated_at`. Ledger sin `UPDATE`, `DELETE` ni `TRUNCATE`.

**Verificar en CI-2** lo anterior, HEAD, tablas/columnas, privilegios y ausencia de `initial_pack_opened_at`. No asumir que el commit reciente modificó la estructura de base. No ejecutar `manage.py` a ciegas: ciertos comandos apuntan a la BD original.

## 3. Regla de autorización: identidad administrativa ≠ rol de una sesión antigua

**Decisión de seguridad para esta etapa:** no conceder beneficios solo porque una sesión tenga `role=PLAYER`. La elegibilidad exige **ambas** condiciones:
1. La **sesión/principal autenticado** tiene rol efectivo exactamente `PLAYER` y el proveedor Google se verificó por los mecanismos vigentes de Identidad; y
2. La **identidad Google estable** (identificada por `provider` + `provider_subject`) **no está clasificada ni reservada como administrativa** por la política central de Identidad.

Implementar/reutilizar **un único criterio central, verificable y probado** en Identidad, expuesto al servicio de Jugadores por puerto o contexto de autorización confiable. No duplicar listas de correos ni parsear JWT en `coleccion_mazos`. El frontend, el `user_id` enviado por el cliente y el mero valor de rol de una sesión histórica **no** son autoridad suficiente para entregar premios. Si hay incertidumbre en el criterio de identidad, fallar cerrado para la entrega, sin crear inventario ni abonar cubos.

**Matriz de decisiones de la política:**

| Identidad/sesión | Elegibilidad para recompensa |
|---|---|
| Google `PLAYER`, `sub` no administrativo, correo no administrativo según identidad confiable | Elegible, si cumple las invariantes económicas |
| `PLATFORM_ADMIN` efectivo, autorizado por correo verificado o por `sub` | Excluido; no jugar ni recibir colección |
| Google `sub` incluido en allowlist administrativa, aunque use Bearer histórico `PLAYER` | Excluido |
| Correo administrativo verificado ligado a la identidad, pero Bearer histórico `PLAYER` | Excluido; una sesión vieja no puede eludir la clasificación de la identidad |
| Correo presente en allowlist administrativa pero verificación ausente/falsa, sin otro respaldo | **Identidad ambigua: no elevar a admin, pero tampoco entregar premios**; exigir reautenticación/verificación y documentar respuesta. Evitar que un reclamo no verificado conceda privilegios. |
| Administrador `LOCAL` | Excluido |
| Rol, identidad o evidencia insuficientes/inconsistentes | No entregar; error controlado con evidencia diagnóstica sin secretos |

**Nota de diseño:** distinguir `PLATFORM_ADMIN` efectivo, la condición de identidad **reservada/excluida** y la evidencia verificable. Investigar qué datos persiste realmente Identidad y cómo conserva el `sub`, el correo y la prueba por sesión; no inventar una columna o API para resolver esto sin inspeccionar código y justificarla. Si no puede lograrse de forma fiable y acotada en CI-2 sin invadir la integración de CI-3, entregar el diseño, pruebas de política y un bloqueo explícito; no dejar una vía que premie administradores. La conexión efectiva de la decisión al login corresponde a CI-3.

**Cambios de estado posteriores:** si un jugador ya recibió beneficios y después es autorizado como administrador, no borrar su inventario ni alterar el ledger; excluirlo de nuevas operaciones de jugador y documentar el caso. No cambiar roles históricos de forma masiva.

## 4. Persistencia y migración sucesora de 012

Reutilizar `player_profiles`, `player_cards`, `cube_transactions`, `catalog_cards`, `catalog_card_images` y las FKs actuales. No crear tablas paralelas ni alterar migraciones históricas.

Proponer y, solo dentro de CI-2 autorizado, implementar **una sucesora nueva de la cabeza real** que añada `player_profiles.initial_pack_opened_at TIMESTAMPTZ NULL` (o nombre equivalente existente si lo hay). `NULL` = paquete sin confirmar. Añadir `CHECK (initial_pack_opened_at IS NULL OR has_received_initial_collection = TRUE)` si los datos actuales y Alembic lo permiten. Los perfiles con beneficios anteriores mantienen `opened_at=NULL`; **no repartir premios de nuevo ni marcar apertura artificialmente**. Probar `upgrade` y `downgrade` en copia/base descartable; no hacer downgrade en la base de uso corriente con datos importantes.

Actualizar el aprovisionamiento versionado para **conceder `UPDATE(initial_pack_opened_at)`** a `orm_media_test` **cuando esa columna exista**, preservando la política mínima ya aplicada. Si el SQL de `manage.py` es general para múltiples entornos, mantener compatibilidad con una instalación en 012; documentar secuencia migración → concesión de permiso. No conceder escritura irrestricta en `player_profiles` ni `UPDATE/DELETE/TRUNCATE` en `cube_transactions`.

**Separación de estados:**
- `has_received_initial_collection=false`, `opened_at=NULL`: aún no se provisionó; esperar catálogo suficiente.
- `has_received_initial_collection=true`, `opened_at=NULL`: premios almacenados, paquete pendiente de confirmación y juego bloqueado.
- `has_received_initial_collection=true`, `opened_at!=NULL`: apertura confirmada; futuros guards podrán permitir juego.
- `has_received_initial_collection=false`, `opened_at!=NULL`: inconsistencia, prohibida por restricción o señalada explícitamente.

CI-2 implementa persistencia y primitivas de estado; los endpoints de consulta, `POST /open` y los guards HTTP son **CI-3**. No afirmar que exista la animación visual.

## 5. Servicio y unidad de trabajo transaccional

Proponer una API interna tipada (nombres finales acordes al repositorio), por ejemplo `asegurar_coleccion_inicial(contexto_autorizado) -> ResultadoProvision`. El contexto debe provenir de Identidad en servidor y resolver `user_id` por el principal autenticado; jamás aceptar `user_id`, cartas, balance, seed o cantidad arbitraria desde un DTO público. Si el servicio recibe `user_id`, solo lo hará mediante puerto interno confiable y comprobará autorización.

**Algoritmo mínimo dentro de una sola transacción PostgreSQL de beneficios:**

```text
BEGIN
  comprobar identidad elegible mediante política de servidor, sin aceptar rol del cliente
  SELECT player_profiles WHERE user_id = :user_id FOR UPDATE
  si el perfil no existe -> error de integridad (no crear perfil fantasma)
  si has_received=true -> ALREADY_GRANTED; no efectuar escrituras de beneficios
  comprobar cubes=0, player_cards vacío y cube_transactions vacío
  si hay inventario, saldo o movimientos previos -> INCONSISTENT_STATE; rollback
  SELECT catalog_cards.id ... JOIN catalog_card_images ...
    WHERE rarity='COMUN' AND state='READY'
      AND referencias original/miniatura válidas
    ORDER BY random() LIMIT 15
  si menos de 15 -> INSUFFICIENT_CATALOG; sin beneficios
  INSERT 15 player_cards (user_id, card_id, quantity=1)
  INSERT cube_transactions (user_id, amount=1000, balance_after=1000,
                             reason=<constante del dominio>)
  UPDATE player_profiles SET cubes=1000,
       has_received_initial_collection=true, updated_at=...
COMMIT
```

El `SELECT ... FOR UPDATE` del perfil debe serializar intentos simultáneos del mismo jugador; volver a evaluar la marca tras adquirir el bloqueo. PK compuesta en `player_cards` aporta defensa adicional, pero no reemplaza el bloqueo. No usar `is_new_user`, `Idempotency-Key` HTTP, locks en memoria, Mongo ni Outbox para decidir si premiar.

Constantes explícitas: `INITIAL_CARD_COUNT=15`, `INITIAL_CUBES=1000`, `INITIAL_COLLECTION` como motivo **solo si coincide con el dominio existente**. Comprobar campos reales, tipos, constraints, joins de imagen y política de códigos. `ORDER BY random()` es aceptable para el catálogo previsto (~10.000); no meter datos sintéticos sin FK para forzar la selección.

La transacción de identidad/sesión ocurre separada de la de beneficios: catálogo insuficiente o fallo económico **no deben eliminar la cuenta ni la sesión**. La semántica de errores, reintentos y respuesta HTTP se termina en CI-3; no reportar la entrega como exitosa cuando hubo rollback. El servicio no debe hacer `commit()` desde adaptadores de bajo nivel. Conservar la separación de dominio, puertos, servicio y adaptador SQL, evitando abstracciones sin consumidores y ciclos de importación.

**Primer movimiento económico:** antes del abono, verificar ausencia absoluta de movimientos de ese perfil e inventario previo. Registrar `+1000` y `balance_after=1000` como primera entrada. No actualizar ni borrar entradas del ledger. Documentar que, hasta terminar el onboarding, cualquier servicio económico debe impedir nuevas transacciones; CI-3 hará cumplir el bloqueo en rutas existentes y nuevas. Evitar suponer que la protección HTTP por sí sola sustituye la protección de los casos de uso económicos.

## 6. Archivos previstos (confirmar HEAD antes de crear)

- Sucesora Alembic de `backend/alembic/versions/012_player_profiles_and_inventory.py` para `initial_pack_opened_at` y restricción compatible.
- Paquete existente o propuesto `backend/src/modules/jugadores/coleccion_mazos/`: dominio (`entrega_inicial_model.py`), puertos (`entrega_inicial_ports.py`), servicio (`entrega_inicial_service.py`) y adaptador SQL (`sql_entrega_inicial.py`), únicamente si faltan implementaciones equivalentes.
- Componente de Identidad/puerto reutilizado para resolver **elegibilidad de identidad administrativa** sin duplicar su política.
- `manage.py` o aprovisionamiento existente: permiso por columna para la marca de apertura, probado sin conectarse a bases originales.
- Pruebas de unidad, integración PostgreSQL real y concurrencia; documentación mínima del contrato.

No editar `frontend/`, `.env`, `.env.example` o equivalentes; el usuario no los versiona. No incorporar credenciales ni rutas privadas en reportes. No agregar Motor, no reescribir login Google/Crear Carta y no ejecutar seed de 50 cartas. No tocar infraestructura/containers productivos.

## 7. Pruebas CI-2 obligatorias

**Unitarias / política:** `PLAYER` normal; `PLATFORM_ADMIN` por `sub`; por correo verificado; histórico `PLAYER` para identidad administrativa; correo administrativo no verificado/claim ausente; administrador local; evidencia inconsistente; no aceptar campos controlados por cliente.

**Integración PostgreSQL aislada:** 0/14/15/50 cartas elegibles; `COMUN` con imagen no `READY` excluidas; referencias de imagen inválidas excluidas; elección de 15 IDs únicos; 1.000 cubos exactos; primer movimiento del ledger; resultado idempotente en reintentos; perfil inexistente o precontaminado rechaza; fallo en inserción N o ledger hace rollback total.

**Concurrencia real:** dos conexiones/transacciones PostgreSQL independientes invocando el servicio para el mismo usuario ⇒ exactamente 15 filas de inventario, **un** movimiento +1000, `cubes=1000` y `has_received=true`; ninguna duplicación. Verificar que la segunda invocación observe `ALREADY_GRANTED` y no dependa de mocks.

**Migración y permisos:** `upgrade` y `downgrade` en BD descartable; comprobar el nuevo `CHECK`, política de `opened_at`, permiso `UPDATE(initial_pack_opened_at)` y que el ledger conserve bloqueados `UPDATE/DELETE/TRUNCATE`. `pytest` no debe ejecutarse contra una base compartida si limpia registros. Ejecutar las regresiones disponibles de Crear Carta e Identidad, Ruff/Mypy si configurados y reportar fallos/skips sin presentarlos como aprobados.

No crear 50 cartas reales para CI-2: ese script y su ejecución autorizada son CI-4. Para las pruebas, utilizar datos aislados transaccionales y cleanup seguro que no altere cuentas reales.

## 8. Salida y condición de cierre

Entregar un reporte con rama/HEAD, archivos leídos y editados, decisiones de arquitectura, diferencias respecto del contrato principal, migración exacta (padre/cabeza), SQL de privilegios, BD usadas con URLs sanitizadas, pruebas aprobadas/fallidas/omitidas, evidencia de concurrencia y rollback, seguridad por identidad/sesión, `git diff --check`, `git status --short` y riesgos pendientes.

Separar claramente **implementado**, **validado en entorno aislado**, **propuesto para CI-3** y **pendiente**. Si la clasificación segura de identidad administrativa necesita una modificación considerable a Identidad o no puede resolverse con el estado persistido, **detener ese subalcance, documentar alternativas y pedir una decisión**; no crear un flujo vulnerable por conveniencia.

**Límite estricto:** ejecutar solo CI-2 una vez autorizado. No conectar aún el servicio a los dos endpoints de login Google, no crear endpoints de apertura ni guards de rutas, no generar el seed, no tocar frontend, no ejecutar migraciones sobre bases originales y no hacer commit/push. CI-3 requiere autorización separada.
