# Poké-Arena — Contrato CI-3: Integración de Google, apertura del paquete y control de acceso

**Historia:** US 3.1.1 — Recibir colección inicial  
**Etapa:** CI-3 exclusivamente, sujeta a autorización expresa  
**Rama de referencia:** `feature/coleccion-inicial` (verificar rama y HEAD reales)  
**Fecha de preparación:** 2026-11-09  
**Alcance:** backend FastAPI, Identidad, Jugadores, composición, endpoints, autorización, pruebas y documentación mínima. **Sin frontend ni seed de 50 cartas.**  
**Estado:** contrato propuesto. No constituye evidencia de implementación ni autorización para ejecutar cambios.

## 1. Base, precedencia y decisión de negocio definitiva

Leer antes de editar: `AGENTS.md`, `ESTRUCTURA-REPOSITORIO.md`, `backend/docs/contracts/INITIAL_COLLECTION_BACKEND_3_1_1.md`, contratos vigentes de Identidad y Crear Carta, migraciones 010–013, servicios/controladores de Google, código de CI-2 y `manage.py`. Verificar el árbol real y las pruebas antes de invocar rutas, nombres, DTO, columnas o interfaces. **Las decisiones explícitas posteriores del usuario prevalecen ante formulaciones anteriores incompatibles.** No borrar ni reescribir contratos históricos para ocultar las discrepancias: documentar la supersesión de reglas y alinear la documentación vigente.

### 1.1. Regla nueva, obligatoria e innegociable: tipo de cuenta inmutable

**Una identidad de Poké-Arena pertenece a una sola categoría durante toda su existencia: `PLAYER` o `PLATFORM_ADMIN`.** Son categorías **mutuamente excluyentes y permanentes**. No existe promoción de jugador a administrador, degradación de administrador a jugador, alternancia por sesión, conversión por cambio de allowlist ni cambio de tipo a través del login.

- La **identidad persistida** es la autoridad del tipo de cuenta. La sesión representa autenticación/autorización de acceso, pero **no puede redefinir** el tipo de la identidad.
- Al registrar por primera vez una identidad Google válidamente verificada, Identidad determina **una vez** el tipo permanente a partir de su política central: administración explícitamente autorizada por `sub` o por correo con `email_verified` **booleano `true`**; en caso contrario, jugador, excepto coincidencias administrativas ambiguas que deben rechazarse sin clasificar ni premiar.
- En ingresos posteriores, Identidad **recupera** el tipo existente, **no lo recalcula** como una asignación nueva ni lo cambia por modificaciones de configuración. Una sesión histórica que alegue otro rol no autoriza acciones incompatibles.
- El administrador, incluso si tiene un perfil técnico heredado o una sesión antigua etiquetada `PLAYER`, **nunca recibe cartas ni cubos** y no accede a funcionalidades exclusivas de jugador.
- El jugador **nunca** obtiene funciones administrativas; no se convierte en administrador porque su correo o `sub` aparezca posteriormente en una allowlist.
- La autorización administrativa vigente puede revocarse o suspenderse sin convertir la cuenta a `PLAYER`. Una discordancia entre clasificación persistida y configuración/credenciales debe **fallar de forma segura** y quedar auditada para corrección explícita de configuración o tratamiento de datos históricos, sin mutación automática de rol.
- **No soportar el escenario de “jugador premiado y posteriormente promovido a administrador”.** La prueba de CI-2 que lo contempla debe revisarse y sustituirse por pruebas que demuestren que esa conversión se rechaza y que el premio previo no se toca.

**Condición de bloqueo previa a la integración:** comprobar cómo persiste realmente Identidad el tipo de cuenta. Si `identity_users` o la fuente persistida autoritativa **no** guarda un tipo estable de forma confiable (p. ej., el rol se deduce solo de allowlists mutables o de una sesión), **no conectar la entrega automática todavía**. Entregar diagnóstico y propuesta de cambio mínimo: reutilización de campo/tabla existente o, si es imprescindible, migración sucesora de `013` con plan de datos históricos y pruebas. Solicitar autorización específica para el cambio de esquema/política antes de aplicarlo; no improvisar una columna, migrar roles en masa ni suponer que la política de CI-2 ya satisface inmutabilidad.

### 1.2. Matriz de identidad y recompensas

| Identidad persistida / situación | Resultado permitido |
|---|---|
| Google nuevo, administración válida por `sub` | Crear/registrar `PLATFORM_ADMIN` permanente; **sin** provisión ni perfil de juego nuevo |
| Google nuevo, correo en allowlist **y** `email_verified=true` | Crear/registrar `PLATFORM_ADMIN` permanente; **sin** premios |
| Google nuevo, evidencia administrativa ausente y sin coincidencia reservada/ambigua | Crear/registrar `PLAYER` permanente; intentar provisión |
| Google nuevo, correo administrativo declarado pero no verificado o claim ausente | **No** elevar ni asignar `PLAYER` de forma oportunista; exigir verificación/recuperación segura, sin premios |
| Google existente `PLAYER`, colección aún no recibida | Mantener tipo y reintentar provisión si catálogo suficiente |
| Google existente `PLAYER`, colección entregada | Mantener tipo; no duplicar; conservar estado de apertura |
| Google existente `PLATFORM_ADMIN` | Mantener tipo; no provisionar ni habilitar rutas de jugador |
| `LOCAL` administrador | Mantener `PLATFORM_ADMIN`; sin provisión ni endpoints `PLAYER` |
| Sesión histórica `PLAYER` ligada a identidad `PLATFORM_ADMIN` | Denegar privilegios de jugador y entrega; reautenticación o manejo seguro de sesión |
| Allowlist cambia de forma incompatible con una cuenta existente | No convertir: conflicto controlado, bloquear privilegios afectados, registrar y conciliar fuera del login |
| Identidad antigua sin evidencia suficiente para clasificar con certeza | No adivinar ni premiar; diagnóstico y decisión específica antes de activación |

**No usar `is_new_user` como criterio económico.** La clasificación ocurre en el alta, pero el premio depende de la marca durable `has_received_initial_collection` y puede reintentarse en logins posteriores si faltó catálogo. La elegibilidad se comprueba siempre contra identidad y sesión confiables del servidor, jamás por correo/rol declarado por cliente.

## 2. Punto de partida y responsabilidades existentes

CI-1 y CI-2 fueron reportadas como completadas. Antes de iniciar, corroborar en el HEAD vigente que están presentes:

- Endurecimiento Google OIDC: autorización por correo únicamente con `email_verified=true` y evidencias asociadas a la sesión; administración por `sub` según política central.
- Arranque sin dependencia residual de Motor; PyMongo asíncrono en Catálogo.
- Servicio interno `EntregaInicial.asegurar(token_sesion)` y composición en `backend/src/modules/jugadores/jugadores_module.py`, con exclusión de identidades administrativas y transacción SQL de beneficios.
- Migración `013_initial_pack_opened_at`, hija de `012_player_profiles_inventory`, columna `player_profiles.initial_pack_opened_at` y CHECK que prohíbe abrir sin provisión; permisos mínimos de `manage.py` para esa columna.
- `player_profiles`, `player_cards`, `cube_transactions`, Catálogo e imágenes `READY` como fuentes SQL; ledger append-only para usuario de aplicación.

**Evidencia reportada de CI-2:** 130 pruebas seleccionadas aprobadas, concurrencia real `GRANTED`/`ALREADY_GRANTED`, rollback y ciclo descartable `012→013→012→013`. Esto no acredita todavía integración HTTP ni Google real. La base aislada habitual `127.0.0.1:15433` **quedó en 012** según reporte; no suponer que ya dispone de 013. Las pruebas de CI-2 usaron bases desechables.

El contrato original proponía mantener la identidad/sesión aun sin catálogo y separar provisión de apertura. **Conservar esa separación.** Cualquier contradicción que impida cumplir los roles permanentes bloquea la activación de CI-3, no se resuelve relajando autorización.

## 3. Alcance exacto de CI-3

Implementar y validar **solo**:

1. Verificación/enforcement de clasificación **persistente, exclusiva e inmutable** `PLAYER`/`PLATFORM_ADMIN` en el flujo real de Identidad, con cambios mínimos y pruebas de regresión.
2. Integración de provisión automática **después** de validar Google y confirmar identidad/sesión, en el **punto compartido** por las rutas de login Google existentes. No duplicar código por endpoint.
3. Consulta autenticada de estado del paquete inicial y sus cartas, sin provocar entrega ni cambios económicos.
4. Confirmación autenticada **e idempotente** de apertura; únicamente marca el paquete abierto y desbloquea funciones de jugador.
5. Dependencia/guard de autorización de funcionalidades de jugador que exija tipo de identidad `PLAYER`, rol/sesión compatibles, beneficios provisionados y apertura confirmada.
6. Pruebas HTTP, integración SQL real, regresión de Identidad/Crear Carta, documentación de rutas y estados.

**Fuera de alcance:** frontend React/Vite, animación y render de paquete, seed de 50 cartas (CI-4), inventar una nueva modalidad de registro, creación de decks, cambios no solicitados en la economía, reestructuración general de Identidad, commits/push automáticos, modificación de `.env`/`.env.example`/variantes, migraciones sobre bases originales.

## 4. Integración con login Google

Inspeccionar los endpoints de Google realmente existentes (incluidas las rutas de emisión/autenticación si son separadas) y ubicar un **punto común de composición**, evitando que una ruta otorgue premios y la otra no.

**Orden obligatorio:**

```text
POST login Google existente
  -> verificar firma, issuer, audience, expiración, sub y email_verified según política OIDC
  -> recuperar identidad o registrarla con tipo permanente PLAYER | PLATFORM_ADMIN
  -> validar que no exista discordancia de tipo/credenciales/sesión histórica
  -> confirmar identidad y sesión propias (transacción actual de Identidad)
  -> si tipo persistente == PLATFORM_ADMIN: OMITIR EntregaInicial, sin perfil de juego nuevo
  -> si tipo persistente == PLAYER y sesión compatible:
       llamar EntregaInicial.asegurar(token_sesion) una sola vez desde composición
       GRANTED / ALREADY_GRANTED -> login autenticado y estado de onboarding disponible
       INSUFFICIENT_CATALOG -> login autenticado; informar indisponibilidad de juego
       INCONSISTENT_STATE / identidad incierta -> no afirmar entrega; error controlado
       excepción de infraestructura -> no afirmar éxito de provisión; registrar y responder error
  -> devolver respuesta compatible con clientes existentes
```

- El servicio de entrega sigue siendo autoridad para idempotencia y atomicidad. No duplicar `SELECT ... FOR UPDATE`, selección aleatoria ni escrituras de beneficios en el controlador de Google.
- **No acoplar** `google_oidc.py` a SQL de Jugadores ni generar dependencias circulares. Preferir interfaz/callback/servicio inyectado en el punto de composición real.
- Las transacciones de sesión y beneficios siguen **separadas**. Si catálogo insuficiente, no se otorgan cartas/cubos y la identidad/sesión pueden persistir; reintento en ingreso posterior. Si falla el premio por causa inesperada, usar respuesta clara (Problem Details o convención existente) y no anunciar onboarding completo; especificar qué ocurre con la sesión confirmada.
- Dos logins simultáneos del mismo `sub` deben resolver **una sola identidad permanente**, no dos perfiles/roles, y una sola entrega. Validar las restricciones únicas reales y conflictos de inserción. No depender de frontend ni `is_new_user` para resolver carrera.
- Mantener el formato/contratos existentes de login y token Bearer opaco. Cualquier ampliación del DTO será aditiva y se probará frente a clientes anteriores; se prefiere el endpoint de estado separado.

## 5. Operaciones HTTP de onboarding (rutas orientativas)

Utilizar convenciones reales del proyecto; documentar **rutas finales** si difieren. Ambas exigen Bearer válido y tipo de identidad **exactamente `PLAYER`**, sin permisos administrativos mezclados.

### 5.1. `GET /api/v1/player/initial-pack` — consulta, sin efectos

- Derivar `user_id` de identidad/sesión del servidor; nunca aceptar uno ajeno del cliente.
- **No** efectuar sorteo, entrega, `INSERT`, cambios de balance, marcado de apertura ni retry económico desde GET.
- Obtener el estado persistido y, si procede, los **15 IDs/códigos** distintos actualmente asignados al jugador desde `player_cards`. No usar `cards_projection` como fuente autoritativa ni leer binarios GridFS.
- Validar coherencia de marca, saldo, inventario y ledger. Una cuenta inconsistente **no** recibe `READY_TO_OPEN`.
- Contrato mínimo de respuesta tipado y estable: `state` como enum, `received` booleano, `opened` booleano, `cards` (vacío si no corresponde), mensaje/código de estado de onboarding cuando sea útil. No exponer correo, Google `sub`, hashes de sesión, secretos ni datos de otro jugador.

| Estado | Condición | Respuesta funcional |
|---|---|---|
| `PENDING_CATALOG` | `has_received=false`; insuficiencia de catálogo u otro estado legítimo de espera ya determinado | No cartas ni cubos; juego temporalmente no disponible; reintentar login posterior |
| `READY_TO_OPEN` | `has_received=true`, `opened_at=NULL`, inventario/saldo/ledger coherentes | Entregar información de las 15 cartas para futura presentación; juego bloqueado |
| `COMPLETED` | `has_received=true`, `opened_at!=NULL`, estado coherente | Paquete ya confirmado; juego autorizado según otros requisitos |
| Error de integridad | Perfil ausente anómalo o datos contradictorios | Error controlado, **nunca** estado listo ficticio |

Si `has_received=false` por error de integridad o fallo previo no diagnosticado, no etiquetar falsamente `PENDING_CATALOG`; definir un error distinguible y verificable. Estado `PENDING_CATALOG` no significa que GET vuelva a sortear.

### 5.2. `POST /api/v1/player/initial-pack/open` — confirmar apertura

- Exigir Bearer válido y categoría permanente `PLAYER`; **no** aceptar `user_id`, cartas, cantidades, saldo, lista de elegidos ni decisiones del cliente.
- Bloquear la fila de `player_profiles` (`FOR UPDATE`) dentro de una **transacción SQL propia** y comprobar que el inventario, la marca y el ledger corresponden a una provisión íntegra. Si no recibió beneficios, responder conflicto/indisponibilidad con código estable; no efectuar provisión en `/open`.
- Si `initial_pack_opened_at IS NULL`, establecer timestamp del servidor una sola vez; si ya tiene valor, devolver `COMPLETED` **sin nueva escritura**, manteniendo timestamp original.
- Respetar CHECK y permiso SQL por columna `UPDATE(initial_pack_opened_at)`. No tocar saldo, cartas ni ledger, ni modificar `has_received_initial_collection` al abrir.
- La confirmación acredita una solicitud autenticada de apertura, **no** prueba que se visualizó una animación. El futuro frontend realizará esta llamada tras su interacción; CI-3 no implementa UI.
- Doble POST concurrente o repetido: único timestamp confirmado y respuesta idempotente; las operaciones no deben crear un segundo premio.

**Errores:** 401 sin sesión válida; 403 identidad administrativa o acceso prohibido; conflicto (p. ej. 409) si paquete pendiente; 5xx/Problem Details para infraestructura o integridad según convención vigente. No inventar 200 para indicar entrega si ocurrió rollback. No filtrar detalles sensibles en errores.

## 6. Guard compartido de funcionalidades PLAYER

Introducir o reutilizar una dependencia de aplicación **explícita y acotada** que valide en servidor:

1. Sesión válida y no revocada.
2. Identidad persistida con tipo **exactamente `PLAYER`**, sin conflicto con evidencia administrativa ni sesión histórica incompatible.
3. Perfil real existente, `has_received_initial_collection=true` y `initial_pack_opened_at IS NOT NULL`.
4. Consistencia mínima de perfil/estado; las operaciones económicas también deben aplicar las invariantes relevantes **en su servicio**, no confiar únicamente en el guard HTTP.

**Proteger** solamente las rutas de juego, inventario avanzado, decks, economía y demás endpoints exclusivos de jugador que ya existan en el HEAD. Inventariar explícitamente cuáles existen y cuáles todavía no; no inventar rutas de ejemplo como implementadas ni alterar endpoints administrativos o Catálogo usados por el administrador.

**Exentos:** login/refresh aplicable, `/identity/me` o perfil mínimo, logout, salud, `GET initial-pack` y `POST initial-pack/open`. El endpoint de estado/apertura sigue siendo exclusivo de `PLAYER`, solo que no requiere paquete ya abierto. No instalar middleware global ni cambiar la semántica de una dependencia como `requerir_jugador` sin auditar usos existentes; si esa dependencia hoy admite admin, **no reutilizarla** como prueba suficiente de tipo `PLAYER`.

Definir códigos HTTP coherentes: ausencia de sesión 401, rol incorrecto 403, paquete pendiente 403/409 según convención que se documente. Evitar que un usuario con paquete pendiente acceda a economía por una ruta no cubierta.

## 7. Roles, perfiles técnicos heredados y datos históricos

- `identity_users` (o fuente equivalente verificada) define la clase permanente de cuenta. `player_profiles` es **estado de juego**, no una autoridad para reclasificar. No crear un perfil nuevo de juego para `PLATFORM_ADMIN` durante CI-3.
- Si el código actual crea `player_profiles` mínimos para **todas** las identidades, comprobar dependencia de login/`identity/me`; corregir solo el alta futura si es seguro y está dentro del alcance, evitando romper endpoints existentes. Un registro técnico heredado para administrador **no** concede elegibilidad. No borrar ni migrar registros heredados automáticamente.
- **Identidades históricas ambiguas:** los `sub` administrativos anteriores al endurecimiento de CI-1 pueden carecer de evidencia suficiente. Antes de habilitar el flujo automático, auditar contra fuentes verificables de Identidad y configuración aprobada, con reporte sanitizado de cantidad/tipos de conflicto; **no** adivinar ni crear listas ocultas/credenciales en código. Si no pueden clasificarse de manera segura, bloquear esa identidad y pedir una conciliación explícita. No transformar cuentas ni premiarlas para “desbloquear”.
- Cambios futuros en `PLATFORM_ADMIN_EMAILS` o `PLATFORM_ADMIN_GOOGLE_SUBJECTS` solo afectan la **admisión de nuevas cuentas** o autorización administrativa conforme política explícita; **no mutan el tipo persistido** de cuentas existentes. Una contradicción se trata como incidencia de configuración y acceso, no como migración automática.
- Una cuenta `PLAYER` con colección ya recibida **permanece `PLAYER`**. No ejecutar ni permitir pruebas funcionales que impliquen su promoción a administrador; reemplazar esas pruebas por controles negativos de inmutabilidad. Una cuenta `PLATFORM_ADMIN` tampoco puede “registrarse nuevamente” como `PLAYER` con el mismo sujeto Google.

## 8. Migración 013, permisos y protección de entornos

Antes de pruebas integradas:

1. Verificar HEAD, rama, `git status`, heads y current de Alembic, estructuras reales, permisos y política de `.gitignore`. Confirmar si 013 ya está aplicada en el destino de **pruebas**.
2. **Preferir PostgreSQL/Mongo desechables aislados** con migración `013` para todas las pruebas que escriban/limpien. Si se propone usar la base aislada persistente `127.0.0.1:15433`, solicitar autorización específica y **hacer backup antes** de aplicar `013`; comprobar host, puerto y base exactos. No usar comandos de `manage.py` que apunten a `5432` por defecto.
3. Comprobar `UPDATE(initial_pack_opened_at)` del rol de aplicación después de 013, `SELECT/INSERT` necesarios sobre inventario/ledger y ausencia de `UPDATE/DELETE/TRUNCATE` de `cube_transactions`.
4. No cambiar migraciones históricas 001–013, no ejecutar `stamp`, `create_all`, `down -v`, borrado de volúmenes ni regresiones destructivas sobre bases compartidas.
5. **Nunca versionar ni alterar** `.env`, `.env.example`, `.env.local` o variantes, en ninguna carpeta. Los archivos locales deben permanecer en el Mac. No mostrar contraseñas, tokens, `Client Secret`, cookies ni `sub` completos en reportes.

Si CI-3 revela que la inmutabilidad requiere una sucesora de esquema de Identidad, **detener esa parte** hasta una autorización específica; no usar una modificación de 013 existente para introducirla.

## 9. Plan mínimo de archivos (sujeto al árbol real)

- Identidad: `backend/src/modules/identidad/gestion_sesiones/{services/sesiones_service.py,adapters/sql_sesiones.py,controllers/sesiones_controller.py,ports/sesiones_ports.py}`, composición `backend/src/modules/identidad/identidad_module.py`.
- Jugadores: `backend/src/modules/jugadores/{jugadores_module.py,coleccion_mazos/services/entrega_inicial_service.py,coleccion_mazos/adapters/sql_entrega_inicial.py}` y controlador/DTO/guard del paquete **solo si no existen equivalentes**.
- API/routers: registrar las rutas en la composición real, sin duplicar endpoints o instanciar servicios SQL al importar módulos.
- Tests: pruebas de identidad inmutable, login Google/HTTP, onboarding GET/open, guard de jugador, permisos y E2E SQL. Reutilizar fixtures existentes de CI-2 y no duplicar repositorios falsos.
- Docs: actualizar contrato principal con decisiones aprobadas (roles inmutables), `AGENTS.md` con fase activa CI-3 y manual de estructura **solo si cambian archivos reales**; README únicamente si cambian API/arranque/variables operativas.

No imponer nombres/carpetas propuestos si el repositorio ya resuelve la responsabilidad con otra composición. Mantener Clean Code, SOLID y DRY, tipos/docstrings en interfaces públicas, sin circularidad entre módulos.

## 10. Pruebas y criterios de aceptación CI-3

### 10.1. Identidad y tipo de cuenta (críticas)

1. Alta Google de `PLAYER` normal → tipo durable `PLAYER`; logins sucesivos conservan tipo; primera provisión únicamente si catálogo suficiente.
2. Alta Google de admin por `sub` → `PLATFORM_ADMIN` durable, sin `player_profiles` nuevo de juego ni recompensa.
3. Alta Google de admin por correo verificado → `PLATFORM_ADMIN` durable, sin recompensa.
4. Correo en allowlist con `email_verified=false` o ausente → ni privilegio admin ni clasificación oportunista de jugador con premio.
5. Cuenta `PLAYER` previa + correo agregado a allowlist → **no promoción**; registrar conflicto y bloquear capacidades indebidas.
6. Cuenta `PLATFORM_ADMIN` previa + correo/sub retirados o Bearer histórico `PLAYER` → **no degradación**; denegar funcionalidades de jugador y resolver acceso administrativo conforme política.
7. Identidad `LOCAL` admin → nunca recibe beneficios ni consulta/abre paquete.
8. Sesión antigua o incompatible con clasificación persistida → 401/403/control de conflicto; no inventario, cubos ni cambio de tipo.
9. Datos históricos ambiguos → falla cerrada, evidencia sanitaria y sin nuevas recompensas.
10. Una identidad Google, incluso con solicitudes concurrentes, mantiene un solo tipo persistente y no crea perfiles duplicados.

### 10.2. Login y beneficios

11. Primer login real de aplicación (Google verificado con JWKS de prueba) de jugador + ≥15 elegibles → sesión y exactamente 15 cartas únicas, `cubes=1000`, primer movimiento `INITIAL_COLLECTION`, marca true, `opened_at=NULL`.
12. 0/14 elegibles → identidad/sesión persistentes, cero premios, estado pendiente; login posterior con ≥15 → único premio.
13. Dos logins simultáneos mismo `sub` → una identidad estable, un solo premio, dos sesiones si la arquitectura permite ambas; sin violación de constraints.
14. Error forzado en el servicio económico → no éxito de provisión falso, cuenta/sesión conservadas según transacciones, rollback íntegro y reintento controlado.
15. Ambas rutas de Google aplicables utilizan el mismo punto de integración; regresiones de DTO y Bearer previos.

### 10.3. Estado, apertura y guards

16. `GET initial-pack` no produce escrituras y devuelve `PENDING_CATALOG`, `READY_TO_OPEN` o `COMPLETED` conforme a estado real; error ante inconsistencias.
17. `POST /open` antes de recibir premio → error controlado; después de provisión → timestamp persistido; repetición/concurrencia → mismo timestamp, sin cambios al inventario/cubos/ledger.
18. Antes de abrir → juego, decks, inventario avanzado/economía protegidos; login, `/identity/me`, estado, apertura y logout siguen disponibles.
19. Después de abrir → autorización de rutas `PLAYER` existentes; `PLATFORM_ADMIN` siempre 403 en estas rutas.
20. Peticiones manipuladas (`user_id`, lista de cartas, balance, flags), Bearer revocado o sesión de otro usuario → rechazo sin filtración ni escritura ajena.

### 10.4. Regresión técnica

21. Verificar `013` en BD de prueba, permisos por columna y ledger append-only.
22. Pruebas con PostgreSQL real de transacciones y carreras; mocks/JWKS simulado como complemento. No presentar Google real como probado si solo se verificó JWKS simulado.
23. Regresiones de Crear Carta (incluido GridFS y Outbox), autenticación Google previa, consultas de Catálogo y migraciones.
24. `git diff --check`, compilación Python, Ruff/Mypy en alcance modificado; detallar aprobadas, omitidas, fallidas y limitaciones.

**Criterio de no cierre:** si el tipo permanente de cuenta no puede demostrarse ni persistirse de forma segura, la integración automática de premios **no puede declararse terminada**, aunque el endpoint devuelva HTTP 200 o los tests de catálogo pasen.

## 11. Entregables, reporte y condición de salida

Codex entregará:

- Rama/HEAD y estado Git inicial/final; archivos leídos, modificados y creados.
- Inventario de rutas Google y de endpoints actuales realmente protegidos; explicación del punto compartido de integración.
- **Evidencia de autoridad persistente del tipo de cuenta**, rechazo de transiciones PLAYER↔PLATFORM_ADMIN y decisión sobre conflictos históricos/configuración. Si falta soporte durable, propuesta de solución y bloqueo explícito.
- Contrato HTTP final de `GET initial-pack` y `POST /open` con DTOs, Problem Details y códigos reales.
- Diagrama/secuencia del login, provisión y apertura; semántica de fallos y reintentos.
- Bases de datos usadas (sin secretos), Alembic antes/después, permisos SQL, backups cuando apliquen.
- Tests por categoría con comandos y resultados, evidencia real de concurrencia e idempotencia; regresiones y riesgos pendientes.
- `git diff --check`, `git status --short`, diff revisado sin secretos y documentación actualizada.

Separar expresamente **implementado**, **probado en aislado**, **no probado con Google real**, **pendiente CI-4** y **bloqueos**. No presentar una animación como implementada.

**Límite de etapa:** no generar 50 cartas (CI-4), no implementar React, no tocar bases originales, no ejecutar comandos destructivos, no introducir cambios de categoría de cuenta, **no commit ni push** y no adelantar CI-4/CI-5. Si aparecen cambios de esquema/política sustanciales para roles permanentes, detener el subalcance y pedir autorización adicional. El cierre de CI-3 no autoriza CI-4.
