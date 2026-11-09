# Poké-Arena — Contrato de ejecución CI-3B

**Historia:** US 3.1.1 — Recibir colección inicial  
**Etapa:** CI-3B — Integración con login Google, estado del paquete, confirmación de apertura y autorización  
**Fecha:** 2026-11-09  
**Rama obligatoria:** `feature/coleccion-inicial`  
**Alcance:** backend exclusivamente; monolito modular hexagonal  
**Estado de este documento:** autorización de alcance para CI-3B; no es evidencia de ejecución ni de validación.

## 1. Contexto verificado y autoridad

CI-1 y su remediación fueron reportadas como finalizadas. CI-2 implementó y probó la provisión interna `EntregaInicial.asegurar(token_sesion)`; CI-3A implementó y probó la inmutabilidad del tipo de cuenta. El árbol de trabajo se reportó limpio y la rama tenía dos commits locales por publicar. Antes de editar, **verificar HEAD, rama y `git status`**: no asumir que el remoto contiene esos commits.

En PostgreSQL **aislado** `127.0.0.1:15433`, base `pokearena_alembic_frontend_dev`, se comprobó la actualización `012 → 013_initial_pack_opened_at → 014_identity_account_immutable`, la columna `player_profiles.initial_pack_opened_at` y el trigger `trg_identity_account_immutable`. Se creó un respaldo y se aplicó manualmente `GRANT UPDATE (initial_pack_opened_at)` a `orm_media_test`; **verificar de nuevo el permiso**, sin darlo por supuesto. No ejecutar migraciones nuevamente si la versión actual ya es 014. **No tocar** PostgreSQL original `:5432`, MongoDB original `:27017`, volúmenes ni credenciales.

La auditoría previa de la base aislada mostró **dos identidades persistidas**: una `GOOGLE / PLATFORM_ADMIN` con perfil técnico sin beneficios y una `LOCAL / PLATFORM_ADMIN` sin perfil. No había `PLAYER` registrados. Esto **no prueba** que las dos cuentas Google administrativas estén ya registradas allí; una podría registrarse en un login posterior.

**Autoridad de requisitos:** decisión expresa del usuario sobre tipos de cuenta permanentes y sobre Yonathan/Fernando como administradores; contrato principal `backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md`; `AGENTS.md`; contratos de Identidad y Crear Carta; migraciones y código verificados. Ante contradicción material, documentarla y detener solo la parte afectada; no resolverla mediante cambios silenciosos de roles, datos ni negocio.

## 2. Decisión definitiva de cuentas y exclusión administrativa

1. Existen exactamente **dos categorías permanentes y mutuamente excluyentes** de cuenta: `PLAYER` y `PLATFORM_ADMIN`. La autoridad durable es `identity_users.role`, asignada **solo al alta**; ninguna variación posterior de listas de administradores, correos, sesiones o endpoints cambia el tipo.
2. **Las cuentas Google de Yonathan y Fernando están destinadas a `PLATFORM_ADMIN`.** Deben estar autorizadas por la política central de Identidad mediante sus entradas aprobadas; para autorización por correo se exige `email_verified` booleano `true`, y la autorización por Google `sub` conserva su política segura actual. Verificar la configuración local efectiva sin mostrar valores sensibles. **No hardcodear correos, `sub` ni secretos** en los módulos de Colección o en los contratos versionados.
3. Si una de esas cuentas **aún no existe**, su primer login válido la registra como `PLATFORM_ADMIN`, **sin** crear un `player_profiles` nuevo y **sin** invocar la provisión. Si ya existe como `PLATFORM_ADMIN`, conserva ese tipo y tampoco recibe beneficios. El `player_profiles` técnico histórico del administrador puede permanecer sin que se interprete como cuenta de jugador.
4. Si una identidad ya registrada como `PLAYER` resulta reservada a administración, **no promoverla**: devolver el conflicto controlado existente, impedir premios y requerir conciliación de configuración/evidencia. Si un administrador pierde autorización vigente, **no degradarlo** a `PLAYER`: rechazar el acceso según la política vigente. La situación de cuenta histórica ambigua se trata con **fail closed**, sin reconstruir evidencia inventada ni borrar datos.
5. Los administradores (Google o LOCAL) **nunca** reciben cartas, cubos ni acceso a rutas exclusivas de jugador. Sus sesiones antiguas o perfiles técnicos no habilitan estas acciones. Un usuario `PLAYER` puede recibir beneficios iniciales solamente una vez.
6. No asumir que `is_new_user` controla la entrega: un jugador nuevo puede encontrar catálogo insuficiente y debe poder recibirla en un **login posterior**; la decisión la toman el estado persistente y el servicio idempotente de CI-2.
7. La inmutabilidad implementada en CI-3A (`014`, trigger, ACL) no se reescribe en CI-3B. Si los contratos de Identidad revelan un fallo, reportar el hallazgo antes de introducir otra política.

## 3. Alcance autorizado de CI-3B

**Sí está autorizado:**

- Integrar el servicio interno CI-2 en **ambas rutas Google** existentes mediante su punto común `_intercambiar_google()` (confirmar nombre/ubicación reales antes de editar).
- Exponer consulta autenticada del estado de paquete y confirmación idempotente de apertura.
- Implementar/reutilizar un **guard específico** para endpoints exclusivos de `PLAYER` y para su estado de apertura; aplicarlo donde corresponda en rutas **ya existentes**.
- Mantener la comprobación centralizada de tipos, sujetos reservados y autorización vigente en Identidad; evitar listas paralelas en Jugadores.
- Añadir DTO, composición, manejo de errores, pruebas y documentación mínima relacionada, sin afectar APIs compartidas.

**No está autorizado:**

- Cambiar tipos de cuenta, reescribir CI-2 o modificar migraciones 012/013/014 históricas.
- Crear el frontend, animación de apertura, hooks React, nuevas funcionalidades de decks/juego/economía no existentes, ni el script CI-4 de 50 cartas.
- Crear/destruir bases compartidas o escribir en los motores originales. No ejecutar seeds sobre usuarios reales.
- Alterar `.env`, `.env.example`, `.env.local` ni variantes; **ninguna se versiona**. No incluir credenciales en pruebas, logs, diffs o documentación.
- Realizar commit o push automáticamente.

## 4. Preflight obligatorio antes de integrar

1. Inspeccionar `AGENTS.md`, `ESTRUCTURA-REPOSITORIO.md`, contrato principal, contratos de Identidad y Crear Carta, revisiones de Alembic y código fuente efectivo de `EntregaInicial.asegurar()`, Identidad, controladores, `jugadores_module.py`, composición FastAPI, rutas y permisos.
2. Verificar **HEAD, `git status`, revision 014 en entorno aislado y ACL**: `orm_media_test` necesita `SELECT`/`INSERT` de inventario/ledger, `UPDATE` restringido en perfil, incluido `initial_pack_opened_at`; no debe poder cambiar `identity_users.role` ni actualizar/borrar ledger.
3. Conciliar el registro Google administrativo actual con la evidencia de autorización aprobada del equipo **sin publicar `sub`, tokens o correos personales**. Confirmar que Yonathan y Fernando figuran como administradores en la configuración privada efectiva; **no inferir que ambos existen en `identity_users`**. Si alguna cuenta persistida contradice el tipo aprobado o carece de evidencia suficiente, bloquear solo la activación de beneficios para esa identidad y documentar la resolución necesaria; no modificar el rol.
4. Confirmar que las dos rutas Google convergen en un único punto de extensión, que la sesión es durable cuando se invoca la entrega y que el retorno de `EntregaInicial.asegurar()` distingue `GRANTED`, `ALREADY_GRANTED`, `INSUFFICIENT_CATALOG` y errores de integridad/internos (adaptar nombres a los tipos reales, no inventarlos como API existente).
5. Mantener **pruebas destructivas en bases desechables**. La base `15433` puede usarse para lectura y comprobaciones controladas, pero no como banco de pruebas que altere identidades existentes. No volver a aplicar `014` si ya está aplicada.

## 5. Integración del login Google

Flujo obligatorio para **ambos** endpoints Google ya existentes, sin duplicar lógica:

```text
Google ID token válido
  → Identity emite/recupera identidad + sesión durables
  → Identity verifica tipo persistido, autorización vigente y conflictos
  → si PLATFORM_ADMIN: responder login normal; NO ejecutar entrega
  → si PLAYER: invocar EntregaInicial.asegurar(token_sesion)
       GRANTED / ALREADY_GRANTED: responder login normal
       INSUFFICIENT_CATALOG: responder login normal; estado pendiente consultable
       fallo de integridad, transacción o dependencia: error HTTP controlado,
           sin fingir entrega exitosa ni exponer Bearer/sujetos en logs
```

- Integrar **después** de persistir identidad y sesión, y después de la clasificación autorizada, respetando las dos transacciones originales: sesión y recompensa pueden persistir por separado; el **premio** continúa siendo atómico (inventario + 1.000 cubos + primer ledger + marca).
- Usar el rol persistido y la política central para la rama administrativa. No basarse exclusivamente en correo de la petición, rol enviado por cliente, `is_new_user`, existencia de `player_profiles` ni un Bearer histórico.
- Un `PLAYER` con `has_received_initial_collection=true` no vuelve a ser premiado, aunque reingrese o tenga paquete sin abrir.
- Menos de 15 cartas elegibles: conservar cuenta/sesión y entregar **cero** beneficios; el próximo login puede reintentar. No conceder premios desde el GET de paquete.
- Fallo real al provisionar: hacer visible el problema con error estructurado seguro y política explícita de reintento; **no** transformarlo en éxito de provisión ni devolver tokens en el error. Revisar compatibilidad con el contrato HTTP del login y documentar cualquier cambio aditivo.
- Admin Google de Yonathan y Fernando: no consultar el inventario ni el paquete para premiarlos, ni crearlos como `PLAYER`. El administrador local mantiene su flujo separado.
- No introducir un flujo HTTP nuevo para el login ni modificar la semántica de alta de CI-3A.

## 6. API del paquete inicial (backend únicamente)

Ajustar prefijos a las convenciones reales; documentar las rutas definitivas en OpenAPI. Se proponen:

| Método y ruta | Comportamiento | Autorización |
|---|---|---|
| `GET /api/v1/player/initial-pack` | Lee el estado de onboarding, sin escribir ni sortear | Bearer válido, tipo persistido **exactamente** `PLAYER` |
| `POST /api/v1/player/initial-pack/open` | Confirma la apertura y desbloquea, de manera idempotente | Bearer válido, tipo persistido **exactamente** `PLAYER` |

**Estados lógicos obligatorios:**

- `PENDING_CATALOG`: el jugador aún no tiene beneficios provisionados. La última entrega pudo encontrar catálogo insuficiente; informar indisponibilidad o necesidad de reintentar login. No mostrar cartas ni declarar entrega realizada. El GET no reintenta provisión.
- `READY_TO_OPEN`: el premio completo existe, `has_received_initial_collection=true` y `initial_pack_opened_at IS NULL`. Devolver las **15 cartas realmente asignadas** en `player_cards` (IDs/códigos y metadatos seguros necesarios para futura UI); no escoger cartas nuevas, no transmitir binarios GridFS ni confiar en identificadores de cliente.
- `COMPLETED`: el premio fue otorgado y la apertura ya fue confirmada (`initial_pack_opened_at IS NOT NULL`). Estado apto para funcionalidades de jugador.

**Invariantes y errores:**

- Detectar y rechazar inconsistentemente almacenado: `opened_at` sin premio; marca de premio con inventario/ledger/saldo anómalos; perfil ausente para `PLAYER` persistido (salvo que un contrato estable documente reparación explícita). No presentar estado exitoso ni reparar silenciosamente.
- Respuestas con DTO tipados y estructura estable, sin filtrar tokens, `sub`, nombres de tablas internos o información sensible. Usar el patrón Problem Details existente para errores `401`, `403`, `409`, `503`/`500` según la causa real; evitar códigos contradictorios.
- GET debe ser solo lectura, no crear cuentas, no abonar cubos, no marcar apertura y no reordenar/sortear premios.

**`POST /open`:**

1. Derivar `user_id` exclusivamente de la sesión autenticada. No aceptar `user_id`, selección de cartas, importe ni `has_received` enviados por el cliente.
2. Exigir `PLAYER` permanente y autorización de sesión vigente. Bloquear el perfil en una transacción SQL.
3. Si todavía no recibió premio, responder conflicto/indisponibilidad; **no** provisionar aquí.
4. Si ya está abierto, responder `COMPLETED` sin nueva escritura (idempotencia).
5. Si recibió exactamente el premio íntegro y sigue cerrado, actualizar solo `initial_pack_opened_at` con fecha UTC de servidor, confirmar y responder `COMPLETED`.
6. Probar dos confirmaciones concurrentes: ambas terminan en el mismo estado, sin movimientos ni entregas nuevas.

## 7. Guards: autorización exclusiva de jugador

Implementar o reutilizar una dependencia de **uso específico** en rutas de jugador que requiera conjuntamente:

- Bearer/session válidos y autorización vigente.
- `identity_users.role == PLAYER` permanente, sin contradicción administrativa.
- `has_received_initial_collection=true`.
- `initial_pack_opened_at IS NOT NULL`.

Antes de abrir, denegar endpoints existentes de juego/decks/inventario avanzado/economía según contrato (`403` u otro estado documentado), pero **no bloquear** login, logout, `/identity/me`, consulta/apertura del paquete, healthcheck ni catálogo compartido de solo lectura. No reutilizar ciegamente `requerir_jugador` porque también permite administradores; no poner un middleware global que rompa Crear Carta o el panel administrativo. Si no existen todavía rutas de juego/economía/decks, reportar explícitamente “sin consumidores actuales”, dejar la dependencia lista y cubrirla con pruebas de autorización; **no inventar rutas ficticias**.

Los administradores Google (ambos) y LOCAL reciben `403` en las rutas exclusivas de `PLAYER`, aunque exista un perfil técnico heredado. No hay camino de conversión de tipos.

## 8. Pruebas obligatorias y condiciones de aceptación

Usar PostgreSQL real y motores **desechables** para pruebas con escrituras; simular JWKS de Google en pruebas automatizadas y distinguirlo de validación con Google real. Reutilizar fixtures de CI-2/CI-3A y el flujo de Crear Carta sin INSERT manual al catálogo real. No ejecutar el seed de CI-4.

1. **Administradores aprobados:** simular por separado la identidad Google de Yonathan y la de Fernando, configuradas de manera segura como administradores; alta nueva o reingreso como `PLATFORM_ADMIN`, **sin** perfil nuevo, colección, cubos ni ledger; endpoints de paquete devuelven `403`. Probar también admin LOCAL.
2. **Cuenta existente:** re-login conserva exactamente su rol. Cambio de allowlist no produce conversión; conflicto administrativo retorna `409 identidad_tipo_en_conflicto` en login según CI-3A, y autorización posterior sigue la política de `403`/`401` apropiada.
3. **Jugador nuevo con 0 o 14 elegibles:** login Google exitoso, un `player_profiles`, `PENDING_CATALOG`, 0 `player_cards`, 0 cubos, 0 ledger, `POST /open` bloqueado.
4. **Reintento del mismo jugador con 15 o 50 elegibles:** segundo login provisiona 15 `COMUN` **distintas** con imágenes `READY` y metadatos canónicos; `cubes=1000`, un primer movimiento `INITIAL_COLLECTION`, marca true, `opened_at=NULL`, `READY_TO_OPEN`.
5. **Idempotencia:** tercer login no cambia premio. Dos logins simultáneos del mismo sujeto no duplican identidad, perfil, cubos ni movimientos; validar con PostgreSQL real y reintentos.
6. **Apertura:** `GET` no muta; `POST /open` confirma una vez; repeticiones y dos aperturas concurrentes devuelven `COMPLETED` sin escritura adicional ni nuevos beneficios.
7. **Guards:** antes de apertura las rutas exclusivas de jugador se rechazan, y tras abrir quedan habilitadas; administradores siguen rechazados siempre. Login, logout, `/identity/me`, catálogo compartido y health permanecen accesibles según sus políticas.
8. **Fallos y rollback:** simular error de inventario y ledger desde integración, comprobar que no quedan beneficios parciales ni exposición del Bearer; siguiente login permite reintentar. Si la sesión ya fue confirmada antes del fallo, documentar el comportamiento y evitar una falsa respuesta de premio exitoso.
9. **Históricos:** tokens administrativos Google antiguos reciben `401` y requieren reautenticación; el perfil técnico admin conservado no permite premio; identidad ambigua/conflictiva queda bloqueada de manera controlada.
10. **Regresión:** las dos rutas Google existentes, admin LOCAL, Crear Carta, GridFS, Catálogo, permisos económicos e inmutabilidad 014 siguen funcionando. Ejecutar pruebas de política, PostgreSQL, integración, Ruff/Mypy/compilación y reportar errores preexistentes por separado.
11. **OpenAPI:** están presentes los dos nuevos endpoints y la documentación de estados/errores; no se anuncian endpoints de juego inexistentes ni frontend listo.
12. **No fingir validación real:** cualquier prueba Google con firma/JWKS simulado se identifica como simulación. La prueba manual con cuentas reales solo se realiza con autorización y fuera de datos compartidos, sin divulgar credenciales ni tokens.

## 9. Permisos y despliegue de prueba

- Verificar que la base aislada `15433` está en `014_identity_account_immutable`. No ejecutar `stamp`, `create_all`, `down -v` ni nueva migración sobre ella sin necesidad.
- Comprobar de nuevo que `orm_media_test` tiene `UPDATE` sobre `player_profiles.initial_pack_opened_at` después del `GRANT` manual; el aprovisionamiento versionado (`manage.py`) debe reproducir ese estado en instalaciones limpias.
- Preservar `SELECT`/`INSERT` de inventario/ledger y `UPDATE` limitado de perfil, sin `UPDATE`, `DELETE` ni `TRUNCATE` sobre `cube_transactions`; sin `UPDATE role`, `DELETE` ni `TRUNCATE` en `identity_users` para la aplicación.
- No escribir pruebas que eliminen cuentas, inventario o cartas en `15433`; para las pruebas de entregas, usar base PostgreSQL desechable y MongoDB desechable únicamente donde Crear Carta lo exija.
- No dar por válida una migración/permiso por el solo éxito de OpenAPI; demostrarlo mediante consulta y pruebas contra el rol real de aplicación.

## 10. Entregables y criterio de cierre

Codex debe entregar un reporte con:

1. Rama, HEAD, `git status`, archivos leídos y modificación justificada por archivo.
2. Confirmación explícita de la política de Yonathan/Fernando administradores y de roles inmutables; diferencias entre cuentas declaradas y cuentas **persistidas** observadas.
3. Flujo concreto donde se llama `EntregaInicial.asegurar()` desde las dos rutas Google y tratamiento de sus resultados/errores.
4. Contratos HTTP definitivos (request/response, estados, guards y errores) y rutas OpenAPI.
5. Pruebas ejecutadas, aprobadas, fallidas, omitidas y su entorno; evidencia de concurrencia, idempotencia, rollback y de que administradores no reciben premios.
6. Comprobación ACL y Alembic `014`, con destinos y usuarios sanitizados; cambios persistidos únicamente en entornos autorizados.
7. Regresiones de Identidad y Crear Carta; riesgos y límites, especialmente problemas de conciliación histórica, pruebas con Google real pendientes y posibles errores previos de Mypy.
8. `git diff --check`, resumen de diff y verificación de que no se agregó ningún `.env` ni secreto.

**Detenerse tras CI-3B**. No comenzar CI-4 (seed de 50 cartas) ni CI-5, no tocar frontend, **no hacer commit ni push**. Si una contradicción de identidad impide habilitar con seguridad la provisión real, informar y detener el flujo afectado, sin reclasificar cuentas.
