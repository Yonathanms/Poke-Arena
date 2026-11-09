# Poké-Arena — Contrato de ejecución CI-4

**Historia:** US 3.1.1 — Recibir colección inicial  
**Etapa:** CI-4 — Catálogo de prueba de 80 cartas e integración real de backend  
**Fecha:** 2026-11-09  
**Rama de referencia:** `feature/coleccion-inicial` (verificar HEAD y estado de Git)  
**Ámbito:** backend y herramienta de desarrollo/pruebas; no frontend  
**Estado:** contrato propuesto para implementación y validación por Codex; no supone trabajo ejecutado.

## 1. Objetivo

Preparar de forma reproducible y segura un catálogo de **80 cartas de prueba nuevas**, mediante el flujo real existente de **Crear Carta**; posteriormente demostrar en un entorno aislado que la integración de la US 3.1.1 permite entregar **15 cartas distintas de rareza `COMUN` con imagen `READY` y 1.000 cubos** a un jugador elegible, una sola vez, y confirmar la apertura sin inconsistencias.

**Cambio aprobado respecto al contrato CI-4 original:** donde antes se proponían 50 cartas `COMUN`, ahora se exigen **80 cartas totales, exactamente 20 de cada rareza**. El resto de las reglas de integridad y seguridad de la US permanece vigente. Actualizar el contrato principal para reflejar esta decisión y eliminar toda referencia a «seed de 50» como requisito vigente, sin reescribir decisiones no relacionadas.

| Rareza de negocio | Cantidad nueva requerida |
|---|---:|
| Común — `COMUN` | 20 |
| Poco común — valor canónico a confirmar (`POCO_COMUN` si corresponde) | 20 |
| Rara — `RARA` | 20 |
| Legendaria — `LEGENDARIA` | 20 |
| **Total** | **80** |

**Importante:** estas cuatro categorías son **rarezas**, no tipos elementales. El tipo elemental de cada carta se puede seleccionar aleatoriamente entre los tipos permitidos por el modelo vigente. No crear una nueva categoría ni modificar enums/checks para satisfacer el seed; verificar los valores exactos del contrato, DTO, validadores y PostgreSQL antes de codificarlos.

## 2. Estado de partida y fuentes de autoridad

- CI-1, CI-2, CI-3A y CI-3B fueron reportadas como completadas; CI-3B todavía debe constar en Git antes de su cierre formal si así lo indica `git status`.
- Se dispone de la migración `014_identity_account_immutable`; en la última verificación la PostgreSQL aislada `127.0.0.1:15433/pokearena_alembic_frontend_dev` estaba en 014. **Verificar de nuevo, no asumir**.
- Se dispone del endpoint real de Crear Carta `POST /api/v1/content/cards`, cuyo contrato multipart, permisos, códigos e `Idempotency-Key` deben inspeccionarse en el código y las pruebas.
- El login Google de `PLAYER` invoca la provisión; `PLATFORM_ADMIN` no recibe beneficios. Las dos identidades Google de Yonathan y Fernando están reservadas a administradores por política de negocio; los tipos son permanentes. No usar sus cuentas para una prueba de entrega.
- La entrega SQL de CI-2 y la apertura de CI-3B deben reutilizarse tal como están; el seed no reimplementa sus reglas.
- Autoridad ante contradicciones: requerimientos de la US y decisiones explícitas del usuario > `AGENTS.md` > contrato principal `INITIAL_COLLECTION_BACKEND_3_1_1.md` > contratos específicos > implementación real y migraciones verificadas. **No solucionar discrepancias alterando silenciosamente el negocio**.

Antes de editar, revisar `AGENTS.md`, `ESTRUCTURA-REPOSITORIO.md`, el contrato principal de US 3.1.1, contratos CI-2 y CI-3B, contratos de Crear Carta e Identidad, el código real de Creación, Outbox, imagen y las migraciones hasta 014. Verificar rama, HEAD, árbol de trabajo y rutas actuales.

## 3. Imagen única de origen

**Ruta obligatoria:** `<raíz de Poke-Arena>/prueba/ip.png`.

- Utilizar **exactamente ese archivo** como fuente para las 80 solicitudes de Crear Carta. El usuario ya comprobó que la imagen cumple el contrato del backend; el script debe verificar que existe y que el validador actual la acepta, sin asumir que una ruta ausente equivale a éxito.
- No generar otras imágenes, no buscar imágenes en Internet y no duplicar el archivo fuente en el repositorio.
- El flujo existente de Crear Carta conserva la responsabilidad de procesar original y miniatura WebP y de escribir los binarios en GridFS. Que todas las cartas usen **el mismo archivo local** no exige compartir un mismo ObjectId en GridFS; dejar que la implementación actual decida los objetos y la limpieza.
- Respetar los límites vigentes del contrato (de referencia: 1–5.000.000 bytes, dimensiones mínimas 600×840, proporción 5:7, máximo 20 Mpx, un fotograma). Si el código real difiere, documentar la discrepancia y usar la validación real; no debilitarla.
- `prueba/ip.png` es material local de prueba. No agregarlo al commit sin decisión expresa; el script debe fallar con un mensaje claro si no está disponible.

## 4. Generación de nombres y atributos

### 4.1 Nombres

- Generar nombres **aleatorios pero reconociblemente relacionados con Pokémon**; usar una lista estática, local y revisable de nombres/especies y calificativos temáticos (p. ej. *Pikachu Chispa*, *Eevee Aurora*, *Charmander Llama*, *Bulbasaur Brote*, *Squirtle Marea*, *Snorlax Siesta*). Se trata de datos ficticios de desarrollo, no cartas oficiales ni afirmaciones sobre la base de datos de Pokémon.
- La variación debe ser **pseudoaleatoria reproducible** a partir de `--seed` (valor por defecto documentado). No depender de servicios externos ni introducir nombres que violen longitud, caracteres o unicidad del DTO.
- Cada carta tendrá un **nombre único y rastreable** con prefijo reservado `CI-SEED-`, identificador estable de lote, rareza, ordinal y elemento temático. Ejemplo conceptual: `CI-SEED-2026A-COMUN-01-Pikachu-Chispa`. Ajustar el formato al límite real de longitud; si es estrecho, abreviar el prefijo conservando trazabilidad y documentarlo.
- Una reejecución con el mismo lote/seed debe generar los **mismos 80 nombres y atributos**; los nombres y las claves de idempotencia deben ser estables por carta.

### 4.2 Otros campos

- Rareza: **fijada por cuota** (20 de cada una), nunca aleatoria entre las cuatro para decidir cantidad.
- Tipo elemental: pseudoaleatorio entre los valores actualmente aceptados (por ejemplo FUE, AGU, PLA, ELE, PSI, LUC, si el código confirma esos valores); procurar diversidad y reportar su distribución.
- `cost`: pseudoaleatorio dentro de **0..10**, sujeto a las restricciones actuales.
- `power`: pseudoaleatorio dentro de **-20..20**, sujeto a las restricciones actuales.
- Habilidad: seleccionar únicamente identificadores realmente existentes y admitidos por Crear Carta. Puede reutilizarse `HAB-000` si se comprueba que sigue disponible, o escoger determinísticamente entre habilidades válidas. **No inventar habilidades ni insertar datos a mano**.
- Cualquier otro campo obligatorio: generar solo valores válidos bajo contrato actual, con `--seed`; si no puede determinarse o no hay dependencias disponibles, abortar con diagnóstico en vez de relajar validaciones.
- Los IDs/códigos de cartas los asigna exclusivamente Crear Carta. No forzarlos desde el seed.

## 5. Implementación del script

Ubicarlo en la carpeta de herramientas/scripts existente del proyecto, una vez inspeccionada; **no** inventar directorios de arquitectura ni modificar `manage.py` por comodidad. Crear un CLI pequeño, documentado y testeable, que reutilice el **mismo caso de uso de aplicación o API HTTP autenticada de Crear Carta**, sin SQL directo para crear cartas.

**Comportamiento CLI propuesto** (ajustar nombres al estilo real y documentar los definitivos):

```text
python <script_real> --dry-run --seed 2026 --image prueba/ip.png
python <script_real> --apply --confirm-isolated --seed 2026 --image prueba/ip.png
```

- Cantidad predeterminada y exigida para CI-4: **80 = 20 por rareza**. No interpretar `--count 80` como 80 cartas `COMUN`.
- **Dry-run por defecto**: comprobar conexiones, esquema, permisos, imagen, datos de entrada, validaciones y el plan de 80 cartas **sin escribir en PostgreSQL, MongoDB, GridFS, Outbox ni identidades**. No lanzar workers con efectos de escritura como parte de un dry-run.
- Escritura únicamente con `--apply` **y una segunda confirmación explícita del destino aislado**. No ejecutar el modo de escritura automáticamente durante el desarrollo ni al arrancar Docker/FastAPI.
- Permitir `--seed` y opcionalmente un identificador de lote estable. El lote debe ser exclusivo del seed para identificar estas 80 cartas y evitar colisiones con otras ejecuciones de desarrollo.
- Operación **reanudable**: antes de crear cada carta, comprobar por una lectura autorizada si la carta propia ya existe. Si existe, validar rareza, atributos esperados e imagen `READY` o estado transitorio; no crear duplicados ni sobrescribir a ciegas. Usar `Idempotency-Key` estable conforme al contrato real.
- Si hay una ejecución interrumpida a mitad, retomar las cartas faltantes y reportar `existentes`, `creadas`, `pendientes` y `fallidas`, con detalle por rareza.
- No borrar registros, reiniciar contadores, limpiar el catálogo ni usar «reset» de bases de datos para recuperar un fallo.
- Manejar errores de forma segura: no imprimir `Authorization`, Bearer, credenciales SQL/Mongo, secretos Google ni respuestas que los contengan. Evitar escribir credenciales a archivos de salida.
- Evitar paralelismo agresivo; comenzar secuencial o con concurrencia muy limitada, justificada por el comportamiento de Outbox, subida y estado READY.

**Prohibiciones explícitas:** INSERT/UPDATE directos a `catalog_cards` para fabricar tarjetas, escrituras manuales a GridFS, compartir ObjectIds a la fuerza, bypass de validaciones, asignación manual de códigos, manipulación directa de counters, emisión manual aislada de eventos de Outbox, ni alterar los repositorios productivos solo para facilitar el seed.

## 6. Protección estricta de los entornos

**Destinos originales intocables:** PostgreSQL `127.0.0.1:5432/pokearena_db`, MongoDB `127.0.0.1:27017` y sus volúmenes originales. Nunca ejecutar seed, migraciones, limpieza ni tests destructivos allí.

Para escritura, validar **las conexiones efectivas**, no únicamente el nombre de `.env` o el nombre del contenedor:

1. Host de ambos motores en loopback (`127.0.0.1` o `localhost` explícito); no URL remota ni puerto original.
2. PostgreSQL con nombre aislado permitido y verificado, como `pokearena_alembic_frontend_dev`; PostgreSQL debe estar en revisión 014 y con permisos previstos para la API.
3. MongoDB con base de desarrollo aislada, como `pokearena_catalog_frontend_dev`, y bucket `card_assets` cuando corresponda.
4. Credenciales y roles de aplicación separados de superusuarios; no usar el rol migrador para crear cartas.
5. La instancia de API a la que se envían peticiones debe estar demostrablemente conectada a esos **mismos destinos aislados**. No basta con que el script compruebe su propia URL si FastAPI apunta a otras bases.
6. Generar backup antes de una ejecución de escritura sobre el entorno aislado persistente; comprobar su legibilidad. No restaurar ni borrar nada automáticamente.

El CI-4 puede programarse y probarse primero contra bases **desechables**. Crear realmente las 80 cartas en el PostgreSQL/MongoDB aislado persistente requiere que el usuario autorice explícitamente esa ejecución tras ver el plan dry-run y el destino. No incluir un `--apply` oculto en pruebas, hooks, startup o comandos globales.

**Archivos privados:** nunca modificar, eliminar, agregar ni versionar `.env`, `.env.example`, `.env.local` o variantes. Conservar las copias locales del usuario; obtener secretos por variables de entorno/procedimientos autorizados sin volcarlos en logs. No subir `prueba/ip.png` por defecto.

## 7. Validación posterior al seed

Tras el `--apply` autorizado, efectuar verificaciones **de solo lectura** sobre la misma instancia donde se crearon las cartas:

- **80 cartas nuevas** identificables por el lote del seed, **20 en cada rareza**, sin duplicación de nombre/código; registros preexistentes no forman parte del conteo de 80.
- Cada una con atributos válidos, habilidad existente, tipo permitido y código generado por Crear Carta.
- Las 80 con imagen `READY` y referencias consistentes a original y miniatura WebP procesadas por el flujo normal.
- Los originales y miniaturas previstos existen en GridFS, con la correspondencia documentada por el contrato actual; no comparar únicamente un contador agregado.
- Outbox y proyección Mongo `cards_projection` procesados según las garantías reales del flujo Crear Carta; si son asíncronos, esperar/pollear con límite explícito y reportar pendientes, no declarar éxito prematuro.
- Reejecución con mismo seed/lote: **0 cartas adicionales** y distribución estable 20/20/20/20.
- Consultar la elegibilidad de la colección con **la misma semántica real del servicio SQL de CI-2**. Confirmar al menos 20 nuevas `COMUN` `READY` elegibles (y por tanto al menos 15), no solo el valor de rareza.
- Los reportes deben distinguir conteo de cartas **nuevas del lote** del total del catálogo.

Si una de las 80 cartas queda fallida/no READY, el resultado es **parcial**, no éxito completo. Reportar qué faltó y cómo reanudar con el mismo seed de forma segura; no crear carta 81 para ocultar un fallo sin autorización.

## 8. Prueba integrada de la US 3.1.1

Usar **bases desechables** y un `PLAYER` de prueba nuevo controlado, con autenticación simulada criptográficamente válida para las pruebas o mecanismo autorizado. No consumir cuentas Google administrativas reales ni crear premios a usuarios existentes por conveniencia. Una prueba manual con Google real requiere una cuenta PLAYER de prueba y configuración segura aparte; no es requisito para fabricar el seed.

Validar como mínimo:

1. Catálogo con 20 cartas nuevas `COMUN` `READY` y otras 60 de rarezas diferentes: un primer login de `PLAYER` provisiona exactamente **15 cartas COMUN distintas**, cantidad 1, y **1.000 cubos** como **primer y único movimiento inicial**.
2. Antes de abrir: `GET /api/v1/player/initial-pack` retorna `READY_TO_OPEN` con las 15 cartas; guard de jugador habilitado deniega juego; administrador devuelve 403.
3. `POST /api/v1/player/initial-pack/open` devuelve `COMPLETED`, y la segunda llamada mantiene el mismo `opened_at`, inventario, saldo e historial.
4. Reingreso: no duplica beneficios. Dos ingresos concurrentes: un único premio. Reintentos con fallo de inventario/ledger: rollback total del premio; identidad/sesión sobreviven.
5. Con catálogo insuficiente (0, 14 elegibles): login exitoso y `PENDING_CATALOG`, sin premios; tras completar catálogo, el login posterior provisiona. Si hay solo 14 COMUN y 60 otras rarezas, estas **no** satisfacen la cuota de elegibilidad.
6. `PLATFORM_ADMIN` (por correo verificado, por `sub` y LOCAL): ninguna entrega; los tipos son permanentes y jamás se convierten. Verificar compatibilidad con un perfil técnico heredado.
7. Regresiones de Crear Carta, Identidad, GridFS, Outbox, Alembic, API de paquete y permisos de base.

**Nota sobre guards:** CI-3B dejó implementado `requerir_jugador_habilitado`, aunque aún no existen rutas productivas de juego/decks/economía/inventario avanzado. No inventar rutas de producción para esta prueba; probar el guard con rutas de fixture o mediante las pruebas de seguridad existentes.

## 9. Pruebas, documentación y criterios de aceptación

- Tests unitarios para generación determinista, límites por rareza, diversidad de nombres, tipos/costos/poder válidos, resolución de habilidad, nombre y clave estable, idempotencia y recuperación parcial.
- Tests de seguridad para `--dry-run` sin escrituras, rechazo de `--apply` sin confirmación, rechazo de bases originales/remotas/ambiguas, API que apunta a motores diferentes y ausencia de credenciales en logs.
- Tests de integración reales en motores desechables: 80 cartas, original/miniatura READY, GridFS, Outbox/proyección, doble ejecución sin duplicados y flujo de paquete con 15 cartas.
- Conservar las pruebas históricas de Crear Carta, Google/Identidad y CI-2/CI-3B; no presentar como aprobadas pruebas omitidas o simuladas.
- `git diff --check`, Ruff, Mypy y compilación en el alcance modificado; documentar errores preexistentes por separado.
- Documentar comando de dry-run y comando de apply con placeholders **sin secretos**. Actualizar `ESTRUCTURA-REPOSITORIO.md` solo con rutas reales; `AGENTS.md` con etapa vigente; contrato principal con 80/20/20/20 y ruta `prueba/ip.png`; README solo si cambia la ejecución de herramienta.
- No modificar frontend; no modificar contratos HTTP de CI-3B salvo corrección mínima justificada, reportada y probada.
- **No commit ni push automáticos. No iniciar CI-5 sin autorización independiente.**

## 10. Forma de entrega obligatoria de Codex

Al finalizar CI-4, reportar:

1. Rama/HEAD y estado de Git al inicio y al final.
2. Archivos leídos, creados y modificados y justificación.
3. CLI definitivo, parámetros, dry-run predeterminado, guardas de aislamiento y comandos reproducibles sin secretos.
4. Valores exactos de rareza y tipo, reglas de imagen y habilidad que confirmó en el repositorio real.
5. Para el seed: estado **no ejecutado / dry-run / aplicado**, base PostgreSQL y Mongo sanitizadas, número de nuevas/existentes/fallidas por rareza, READY, GridFS, Outbox y proyección.
6. Resultado y evidencia de pruebas de idempotencia, concurrencia, rollback, catálogo insuficiente, admin/jugador, apertura, seguridad y regresión; indicar motores reales versus simulados.
7. Riesgos, inconsistencias y permisos pendientes; estado Alembic de cada base usada.
8. Confirmación de que bases originales, archivos `.env` y `prueba/ip.png` no fueron alterados y de que no hubo commit/push.

**Bloqueo de avance:** si Crear Carta no admite una de las cuatro rarezas exactas, si la habilidad no existe, si el flujo de imagen no alcanza `READY`, si no se pueden garantizar los destinos aislados, o si hay una incompatibilidad grave de permisos/identidad, detener el `--apply` y reportar evidencia y opciones. No forzar datos ni debilitar validaciones para terminar las 80 cartas.
