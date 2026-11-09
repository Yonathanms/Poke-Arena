# Poké-Arena — Contrato de ejecución CI-5

**Historia:** US 3.1.1 — Recibir colección inicial  
**Etapa:** CI-5 — Auditoría integral, regresiones y cierre del backend  
**Fecha:** 2026-11-09  
**Rama de referencia:** `feature/coleccion-inicial` (verificar rama, HEAD y estado de Git)  
**Ámbito:** backend exclusivamente; monolito modular hexagonal; PostgreSQL, MongoDB y GridFS aislados  
**Estado:** contrato de ejecución concluido en CI-5E. Los resultados y las observaciones constan en el [informe de cierre](CI_5_INFORME_CIERRE_BACKEND.md).

## 1. Objetivo y regla de autoridad

Auditar de extremo a extremo la implementación de **US 3.1.1 — Recibir colección inicial** realizada en CI-1, CI-2, CI-3A, CI-3B y CI-4; detectar regresiones, inconsistencias, vulnerabilidades y documentación desactualizada; emitir un **dictamen verificable de cierre**. CI-5 es una fase de validación y corrección mínima de defectos demostrados, **no de desarrollo de funcionalidades nuevas**.

Son invariantes no negociables:

- Un `PLAYER` elegible recibe **exactamente 15 cartas diferentes**, todas `COMUN` y con imagen `READY`, seleccionadas por el servidor, y **1.000 cubos**, una sola vez y en una transacción lógica todo-o-nada.
- El abono inicial de cubos es **el primer movimiento** del historial de ese jugador; no puede duplicarse por concurrencia, reingresos ni reintentos.
- Con menos de 15 cartas elegibles, login y sesión pueden existir, pero el premio permanece pendiente sin entregas parciales y se reintenta en un login posterior.
- El flujo del jugador es **login → paquete disponible → apertura confirmada → endpoints protegidos habilitados**. Antes de abrir, los guards bloquean acciones de jugador no permitidas, sin impedir identidad, consulta del paquete o cierre de sesión.
- `PLAYER` y `PLATFORM_ADMIN` son categorías **permanentes e incompatibles**. El valor persistido de `identity_users.role` no cambia por variaciones de allowlist, correo, sesión ni por un login posterior. Ningún administrador —Google o LOCAL— recibe premios ni acceso a rutas exclusivas del jugador.
- La apertura es idempotente; no vuelve a conceder premios y mantiene inalterada la marca de apertura original ante llamadas repetidas.
- El catálogo de CI-4 contiene **80 cartas nuevas del lote `CI4-2026`**, 20 por cada rareza (`COMUN`, `POCO_COMUN`, `RARA`, `LEGENDARIA`), generadas por el flujo real de Crear Carta con imágenes originales y miniaturas en GridFS y proyección eventual en MongoDB.

**Autoridad:** requisitos oficiales de la US y decisiones explícitas del usuario; `AGENTS.md` vigente; contrato principal `backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md`; contratos específicos de CI-3B y CI-4; contratos de Identidad, Crear Carta, Outbox y sus migraciones; implementación real. Si la documentación y el código discrepan, levantar hallazgo y comprobar la intención aprobada; no cambiar reglas de negocio silenciosamente.

## 2. Estado conocido antes de CI-5: evidencia a reconfirmar

Durante la ejecución manual de CI-4 del **2026-11-09**, se reportó en los motores aislados:

| Elemento | Evidencia observada |
|---|---:|
| Cartas totales en `catalog_cards` | 82 |
| `COMUN` / `POCO_COMUN` / `RARA` / `LEGENDARIA` | 20 / 20 / 22 / 20 |
| Nuevas cartas del lote CI-4 | 80, distribuidas 20/20/20/20 |
| Pares original/miniatura registrados por el seed | 80 |
| Eventos `CardCreated` en `shared_outbox` | 82 `PROCESSED`, 0 `PENDING` |
| Documentos en MongoDB `cards_projection` | 82 |
| Imagen fuente del seed | `prueba/ip.png` |
| Parámetros del seed | `--seed 2026 --lote CI4-2026` |

La diferencia de dos cartas `RARA` proviene de registros anteriores al seed. **No deducir integridad únicamente de la igualdad de contadores.** Verificar por identificador/código, estado `READY`, referencias de archivos, Outbox y proyección **una a una** para las 80 cartas. No confundir estos datos observados con resultados ya ejecutados por CI-5.

**Pendiente de demostrar en CI-5:** recorrido integral de un `PLAYER` nuevo y sus casos negativos, concurrencia, rollback, autorización e inmutabilidad, y ausencia de regresiones. La autenticación Google real de una cuenta `PLATFORM_ADMIN` ya se observó, pero **no prueba** el onboarding de un `PLAYER` real.

No suponer que el commit propuesto de CI-3B + CI-4 se realizó: verificar `git log`, `git status` y diferencia respecto de `origin/feature/coleccion-inicial`. No hacer `git push` para sincronizarlo por cuenta propia.

## 3. Protección del entorno y alcance

**Bases originales intocables:** PostgreSQL `127.0.0.1:5432/pokearena_db` y MongoDB `127.0.0.1:27017`, incluidos sus volúmenes, usuarios, secretos y datos.

**Motores aislados persistentes de referencia:**

- PostgreSQL: `127.0.0.1:15433/pokearena_alembic_frontend_dev`.
- MongoDB: `127.0.0.1:27029/pokearena_catalog_frontend_dev`.
- GridFS: bucket `card_assets`.
- Worker Outbox: utiliza `DATABASE_URL`, `MONGO_URL` de **proyección** y `MONGO_DB`; no asumir que la variable especial `CI4_PROJECTION_MONGO_URL` se consume automáticamente por el worker.

Condiciones obligatorias:

1. Antes de cualquier conexión, comprobar **destinos efectivos** de FastAPI, scripts, worker y pruebas. La lectura del nombre de un `.env` no equivale a verificar el destino.
2. La base aislada persistente se usa por defecto **solo para lecturas y auditoría no destructiva**. Las pruebas que creen usuarios, sesiones, inventarios, movimientos, cartas, aperturas o fallos forzados deben ejecutarse en **clones desechables** o un banco de pruebas específicamente autorizado. No ensuciar ni reinicializar la base persistente para completar CI-5.
3. Prohibido `docker compose down -v`, borrado de volúmenes, `drop`, `truncate`, `stamp`, `create_all` o migraciones destructivas sobre motores compartidos/persistentes. No repetir `--apply` del seed ni reconstruir las 80 cartas.
4. No cambiar ni versionar `.env`, `.env.local`, `.env.example` o variantes; tampoco secretos, tokens Bearer/Google, `sub`, credenciales, backups ni `prueba/ip.png` sin autorización específica. Nunca imprimir URLs con contraseñas ni cabeceras `Authorization`.
5. No crear ni usar cuentas personales administrativas reales para pruebas de premio. Las pruebas de usuario deben usar un `PLAYER` de laboratorio en una base desechable con autenticación de prueba válida. El ensayo con **Google real de un PLAYER independiente** requiere autorización y configuración explícitas aparte; no es un requisito para comenzar CI-5.
6. No modificar frontend, agregar nuevas APIs, introducir migraciones históricas, redefinir roles o cambiar el contrato funcional para hacer pasar pruebas. Cualquier corrección funcional mínima necesita evidencia del defecto, test de regresión y explicación de alcance.
7. **No commit ni push automáticos.** Solicitar autorización expresa antes de modificaciones materiales y antes de cualquier publicación.

## 4. Plan de ejecución de CI-5

### CI-5A — Preflight y revisión estática (solo lectura)

- Leer `AGENTS.md`, `ESTRUCTURA-REPOSITORIO.md`, README y contratos relevantes de US 3.1.1, CI-3B, CI-4, Identidad, Crear Carta y Outbox.
- Registrar rama, HEAD, commits locales, archivos cambiados/no rastreados, versiones de herramientas y configuración de pruebas.
- Inspeccionar rutas reales de login Google, `GET /api/v1/player/initial-pack`, `POST /api/v1/player/initial-pack/open`, dependencias/guards, `EntregaInicial.asegurar`, consultas SQL, marca `initial_pack_opened_at`, repositorios, sesiones y worker.
- Verificar migración `014_identity_account_immutable` y permisos de aplicación, particularmente que el rol no pueda actualizarse y que la apertura disponga del permiso mínimo requerido.
- Revisar transacciones, bloqueos y condiciones de carrera, DTO y códigos HTTP, validación del principal autenticado, errores seguros, logs y ausencia de acceso de administradores a recursos `PLAYER`.
- Revisar el historial de CI-3B/CI-4 y determinar qué requisitos están cubiertos por tests y cuáles solo por afirmaciones documentales.

**Entregable:** matriz requisito → archivo/función → prueba → evidencia → estado, y lista de riesgos/bloqueos. Si surge un problema crítico de aislamiento o autorización, detener las pruebas con escrituras.

### CI-5B — Regresiones automatizadas

Ejecutar, con motores desechables correctamente identificados, las suites de colección inicial, apertura HTTP, seed, Identidad, Crear Carta, imágenes, Outbox y otras áreas impactadas. Al menos revisar y ejecutar donde proceda:

- `backend/tests/test_initial_collection_postgresql.py`
- `backend/tests/test_initial_pack_http.py`
- `backend/tests/test_ci4_seed_cartas.py`

Descubrir y ejecutar las pruebas adicionales **realmente existentes**; no inventar nombres ni afirmar cobertura basándose solo en ficheros. Incluir las verificaciones del proyecto para compilación, Ruff, Mypy, integridad de imports y `git diff --check`, según configuración instalada. Separar fallos preexistentes de regresiones introducidas. Un test omitido (`skip`), simulado o que no conectó a sus motores **no cuenta como integración real aprobada**.

### CI-5C — Pruebas funcionales de extremo a extremo

En **bases desechables** y con identidades de laboratorio, ejecutar y verificar con lecturas de PostgreSQL y de la API:

1. `PLAYER` nuevo + al menos 15 cartas `COMUN` `READY`: primer login válido concede exactamente 15 **IDs distintos** de rareza `COMUN`, una unidad de cada carta, 1.000 cubos y **un único movimiento inicial que es el primero del historial**.
2. Estado previo a apertura: `GET /api/v1/player/initial-pack` devuelve el estado canónico de paquete listo (por ejemplo `READY_TO_OPEN` si así lo define el código), y las rutas protegidas bloquean el acceso antes de abrir.
3. `POST /api/v1/player/initial-pack/open`: transita al estado final canónico (`COMPLETED` si corresponde) y habilita solo los endpoints autorizados. Repetir POST: mismo `opened_at`, mismas cartas, cubos y movimientos.
4. Segundo login y llamadas duplicadas: no generan premios, nuevos movimientos ni aperturas adicionales. Dos primeros logins simultáneos deben producir **una única entrega**.
5. Catálogo insuficiente (0 y 14 `COMUN` `READY`): identidad y sesión válidas, estado `PENDING_CATALOG`, sin inventario ni cubos de regalo; después de completar la elegibilidad, un ingreso posterior provisiona **una sola vez**. Las rarezas no comunes y las imágenes no `READY` no cuentan.
6. Inyección de fallo después de parte del inventario o del movimiento: rollback total de la entrega; el reintento posterior logra una entrega única. No dejar marcas de provisión ni movimientos parciales.
7. `PLATFORM_ADMIN` Google y LOCAL: sin concesión de beneficios y 403/estado canónico ante rutas de jugador. Comprobar el caso de administrador con `player_profiles` técnico histórico.
8. Roles inmutables: cambiar allowlists después del alta, simular pérdida de autorización y comprobar que **nunca se actualiza** `identity_users.role`; si corresponde, se rechaza acceso de forma controlada. Un `PLAYER` existente no se convierte en admin ni viceversa.
9. Seguridad: principal de sesión determina identidad y permisos; no aceptar `user_id`, IDs de cartas, rarezas, cubos o banderas de apertura enviados por cliente para alterar el beneficio. Probar sesión caducada, ausente, inválida y acceso cruzado.
10. API Google: confirmar que ambas rutas válidas reutilizan el mismo flujo común y la misma semántica de provisión, sin relajar verificación OIDC de `aud`, `iss`, `exp`, `sub` y política de correo verificado cuando aplique. Usar pruebas controladas, no tokens compartidos.

Registrar para cada caso el **test o escenario**, resultado real, consultas/asser­ciones, códigos HTTP canónicos verificados y evidencia sanitizada. No asumir nombres de estados ni endpoints adicionales sin cotejar código.

### CI-5D — Reconciliación de datos CI-4 (lecturas sobre el entorno aislado persistente)

- Ejecutar el **dry-run** del seed con el mismo `--seed 2026 --lote CI4-2026` y comprobar 20 existentes por rareza, 0 por crear, 0 fallidas, sin escrituras.
- Consultar por nombre/clave de lote las 80 cartas, su unicidad, códigos, atributos, habilidad y estado de imagen `READY`.
- Verificar para **cada carta** existencia y consistencia de los dos objetos esperados en GridFS y de su documento en `cards_projection`; no limitarse a `COUNT(*)` global.
- Validar que los 80 eventos correspondientes están `PROCESSED`, que no existen fallos no conciliados y que el worker no dejó leases atascados.
- Reconciliar el total observado de 82 cartas SQL / 82 proyecciones MongoDB / 82 eventos procesados, distinguiendo 80 nuevas y 2 previas. Si existen cambios concurrentes, registrar su origen y ajustar la lectura, no forzar números.
- Comprobar que al menos 15 cartas `COMUN` con imagen `READY` cumplen **la consulta de elegibilidad real de CI-2**; la evidencia anterior apuntaba a 20.
- Confirmar que el seed no alteró las bases originales, que no hay duplicados ni escrituras adicionales por este control y que los backups previos siguen identificados/legibles sin restaurarlos.

### CI-5E — Documentación, revisión final y dictamen

- Revisar `README.md`, `AGENTS.md`, `ESTRUCTURA-REPOSITORIO.md`, contrato principal y contratos de etapa. Corregir solo inconsistencias confirmadas: cantidad vigente **80 = 20/20/20/20** (no la propuesta obsoleta de 50), rutas, comandos realmente verificados, rol inmutable, guards, permisos y flujo de apertura.
- Auditar `git diff` y archivos no rastreados: ningún secreto, `.env`, imagen privada, dump o artefacto de prueba debe incorporarse inadvertidamente. Mantener Clean Code, SOLID, DRY, tipado y docstrings relevantes.
- Documentar defectos encontrados, correcciones mínimas realizadas, pruebas de regresión y riesgos residuales; distinguir evidencia real de pendiente/no ejecutada.
- Emitir uno de estos dictámenes: **APROBADO**, **APROBADO CON OBSERVACIONES** o **BLOQUEADO**. Un bloqueo funcional/seguridad/integridad/aislamiento impide declarar cierre completo aunque otras pruebas pasen.
- Recomendar, pero **no ejecutar automáticamente**, commit, push, merge ni apertura de trabajo frontend.

## 5. Criterios de aceptación del cierre

CI-5 puede declararse **APROBADO** solo si:

1. Los requisitos funcionales y de seguridad de la US 3.1.1 están cubiertos por evidencia verificable, incluidos concurrencia, idempotencia, rollback, catálogo insuficiente, apertura y roles permanentes.
2. El backend de Identidad, Crear Carta y Outbox no presenta regresiones relevantes; las pruebas de integración identifican claramente motores reales frente a dobles de prueba.
3. Se reconciliaron las 80 cartas CI-4, imágenes `READY` y GridFS, Outbox y proyección Mongo sin discrepancias no explicadas.
4. Las pruebas no generaron cambios no autorizados en el entorno aislado persistente ni tocaron bases originales.
5. La documentación refleja la implementación vigente y no hay secretos ni artefactos privados incluidos en Git.
6. Todos los hallazgos críticos y altos están corregidos y revalidados, o el dictamen permanece **BLOQUEADO**; los riesgos menores quedan expresamente documentados.

## 6. Forma obligatoria del informe final de Codex

Entregar [`CI_5_INFORME_CIERRE_BACKEND.md`](CI_5_INFORME_CIERRE_BACKEND.md) según la autorización documental de CI-5E, con:

1. Rama/HEAD, estado Git inicial y final, commits locales/remotos y archivos inspeccionados/cambiados.
2. Matriz de requisitos ↔ implementación ↔ pruebas ↔ resultado (PASÓ / FALLÓ / OMITIDO / NO EJECUTADO), sin contabilizar skips como éxitos.
3. Identificación sanitizada de las bases usadas y prueba de aislamiento efectivo de FastAPI, scripts y worker.
4. Resultados exactos de CI-4: 80 por lote, distribución 20/20/20/20, READY, GridFS, Outbox y proyección; explicar las 2 cartas preexistentes.
5. Evidencia de casos E2E, escenarios de error, concurrencia, idempotencia, inmutabilidad, guards y permisos, con aserciones y resultados HTTP reales.
6. Suites ejecutadas, cantidad de aprobadas/fallidas/omitidas, herramientas de calidad, fallos existentes y comandos de reproducción sin secretos.
7. Hallazgos priorizados (CRÍTICO/ALTO/MEDIO/BAJO), correcciones realizadas o propuestas, archivos afectados, riesgos residuales y bloqueos.
8. Dictamen final motivado y recomendación sobre preparación del backend para integración frontend.
9. Confirmación explícita: sin writes a originales, sin cambios secretos, sin `--apply` extra, sin commit/push automático.

## 7. Instrucción operativa para Codex

**Ejecuta CI-5 según este contrato, comenzando por CI-5A (solo lectura).** Verifica el repositorio y las bases aisladas reales en lugar de asumir que el estado descrito sigue vigente. Presenta un diagnóstico y la matriz de pruebas antes de ejecutar integraciones con escritura. Puedes realizar pruebas puramente estáticas/no destructivas; solicita autorización separada para levantar o modificar clones desechables, ejecutar escenarios E2E con escrituras, modificar código/documentación o usar una cuenta Google real de prueba. No inventes resultados ni cambies funcionalidades fuera de alcance. Si hay un defecto crítico, detén solo la operación afectada y explica la evidencia, el impacto y la remediación mínima propuesta. **No hagas commit ni push.**
