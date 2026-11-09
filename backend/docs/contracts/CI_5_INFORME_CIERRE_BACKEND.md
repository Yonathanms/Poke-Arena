# CI-5E — Cierre del backend de Recibir colección inicial

**Proyecto** Poké-Arena · **Historia** US 3.1.1 · **Fecha** 2026-11-09

**Dictamen: APROBADO CON OBSERVACIONES.** El backend está preparado para integrar el onboarding en React. Se demostraron la separación de cuentas, la provisión atómica, la apertura persistente y la integridad de `CI4-2026`. Las observaciones de operación y calidad se detallan al final. El ensayo con Google real para un jugador y la integración de React están pendientes de autorización.

## Revisión de Git y del alcance

- Rama `feature/coleccion-inicial`, HEAD auditado `7f0bccd5643e1eeca43033d8ad9f86081a6c94c9`. Árbol inicial limpio. Base común con la referencia local `origin/development` y punta local de seguimiento de la rama `2af171ece4e3dd46aeff35163de0779c226f69d7`.
- Cuatro commits en el rango local `2af171e..HEAD`: `b105419` (CI-1), `1b5a3ab` (CI-2 y CI-3A), `cb7b330` (CI-3B y CI-4) y `7f0bccd` (CI-5B.1 y contrato CI-5). El rango acumula 46 rutas. El estado de publicación se refiere a las referencias disponibles localmente.
- El cierre modifica únicamente [AGENTS.md](../../../AGENTS.md), [ESTRUCTURA-REPOSITORIO.md](../../../ESTRUCTURA-REPOSITORIO.md), [README.md](../../../README.md), el [contrato principal](INITIAL_COLLECTION_BACKEND_3_1_1.md), el [contrato CI-5](CI_5_CONTRATO_AUDITORIA_FINAL_BACKEND.md) y este informe. Los seis cambios quedan locales y sin preparar para commit.
- Las migraciones históricas de la base se conservaron. El rango añade `013_initial_pack_opened_at` sobre `012_player_profiles_inventory` y `014_identity_account_immutable` sobre `013`. `alembic heads` verificó una sola cabeza, `014`. Su aplicación en el aislado persistente fue confirmada en CI-5D.
- El inventario de rutas y la revisión de adiciones de cada commit mediante patrones de claves privadas, credenciales de proveedor, JWT, URIs y literales de contraseña encontraron solo datos sintéticos en pruebas entre las coincidencias nuevas. El rango elimina las dos plantillas `.env.example`; no incorpora archivos de entorno, imagen privada, respaldo ni artefacto temporal. La inspección detectó valores fijos de desarrollo ya presentes en `manage.py` en la base. Se retiró su reproducción en las instrucciones de README. La validez de esos valores en instalaciones existentes queda sin verificar.

## Matriz de requisitos y evidencia

| Requisito | Implementación | Evidencia | Resultado |
|---|---|---|---|
| Alta PLAYER y separación administrativa | `Sesiones.emitir`, `SqlSesiones.crear`, callback de `jugadores_module` | CI-5C, ambas rutas Google `200/201`, identidad, perfil y sesión verificados en SQL. Google y LOCAL admin obtuvieron `403` en las rutas exclusivas y cero beneficios, incluido un perfil técnico histórico. | PASÓ |
| Tipo y clave estables | `SqlSesiones`, trigger y ACL de `014` | Cambiar allowlist produjo `409` en ingreso y `403` en sesión existente sin reclasificar. Los intentos SQL de cambiar rol o `provider_subject` fueron rechazados. | PASÓ |
| Sorteo de 15 comunes distintas desde el servidor | `SqlTransaccionEntregaInicial.seleccionar_cartas` | CI-5C comprobó 15 IDs distintos `COMUN`/`READY`, cantidad 1, y exclusión de rarezas, imágenes pendientes y referencias inválidas. Campos de control enviados por cliente se rechazaron con `422`. | PASÓ |
| 1.000 cubos y primer movimiento | `EntregaInicial.asegurar`, `registrar_entrega`, tablas de `012` | SQL confirmó saldo de 1.000 y un único primer movimiento `INITIAL_COLLECTION` por 1.000. El rol de aplicación pudo insertar y leer el ledger y carecía de permisos para editarlo, borrarlo o truncarlo. | PASÓ |
| Catálogo insuficiente y reintento | `EntregaInicial.asegurar`, `PaqueteInicial.consultar` | Con 0 y 14 elegibles, GET devolvió `PENDING_CATALOG` y abrir devolvió `409 paquete_pendiente`. SQL confirmó cuenta sin beneficios. El siguiente ingreso con catálogo suficiente otorgó el premio. | PASÓ |
| Atomicidad y concurrencia | Unidad de trabajo SQL y bloqueo de perfil | Dos primeros logins dejaron un solo premio. Fallos inducidos durante inventario y durante y después de insertar el movimiento dieron `503`, rollback total de beneficios y reintento correcto. | PASÓ |
| Consulta y apertura idempotente | `PaqueteInicial`, rutas `/api/v1/player/initial-pack` y `/open`, columna de `013` | GET `READY_TO_OPEN` sin mutar datos. Dos aperturas simultáneas y las repeticiones devolvieron `COMPLETED` con el mismo `opened_at`. | PASÓ |
| Premio cerrado inconsistente | Validación compartida entre provisión y apertura | Cantidad, saldo o movimiento alterados produjeron `409` sin reparar ni duplicar el premio. El reingreso no entregó Bearer en ese error. | PASÓ |
| Guard y recursos mutables después de abrir | `requerir_jugador_habilitado` y marca de apertura | Ruta de prueba con el guard real dio `403` antes y `200` después. Una carta adicional y un gasto simulado en SQL conservaron acceso, timestamp y movimiento original. | PASÓ |
| Sesión y aislamiento entre jugadores | Bearer opaco, verificación central de Identidad y DTOs sin identificadores controlables | Sesión ausente, inválida, vencida o revocada obtuvo `401`; el intento cruzado obtuvo `422` y no alteró el perfil ajeno. | PASÓ |
| OIDC y logs | `google_oidc` y controlador de sesiones | JWT y JWKS controlados comprobaron firma, `iss`, `aud`, expiración, `sub` y correo verificado para la autorización por correo. Las pruebas de CR/LF y excepciones no expusieron JWT ni marcadores sensibles. | PASÓ |
| Crear Carta, imágenes y Outbox | API multipart autenticada, GridFS y worker independiente | El recorrido de CI-5C creó 17 cartas de laboratorio por HTTP, verificó 34 objetos y 17 eventos y proyecciones. CI-5D concilió por carta el lote persistente. CI-5B.1 verificó que el validador del worker rechaza los puertos originales y topologías ambiguas. | PASÓ |
| Login con proveedor real para un PLAYER y consumidores de juego | Dependencias y contratos disponibles | No se usaron cuentas reales. El guard no tiene consumidores productivos de mazos, inventario avanzado, juego ni economía. | NO EJECUTADO / FUERA DEL ALCANCE |

## Pruebas e aislamiento

| Etapa | Resultado registrado |
|---|---|
| CI-5A | Revisión estática y preflight. Se detectaron cuatro riesgos funcionales o de seguridad y deuda de análisis estático. |
| CI-5B | 331 aprobadas, 1 fallida, 1 omitida. Las caracterizaciones reprodujeron los cuatro riesgos. El test fallido leía como literal una constante de la migración 013. |
| CI-5B.1 | 341 aprobadas, 0 fallidas, 1 omitida. Corregidos los cuatro riesgos y el test estático. Los 11 casos originales se reejecutaron con expectativas corregidas. Se omitió la prueba que reconstruye las 80 cartas. |
| CI-5C | 54 aprobadas, 0 fallidas, 0 omitidas dentro de la selección. 27 colección/apertura, 13 Identidad, 12 OIDC/logs, 1 recorrido HTTP por socket, 1 rollback posterior al movimiento. 35 casos del archivo de Crear Carta quedaron fuera del filtro OIDC. |
| CI-5D | Preflight, dry-run y 80 conciliaciones individuales de solo lectura, sin anomalías. |
| CI-5E | Revisión documental, auditoría Git y estática, y lectura de respaldos sin restauración. |

Las suites CI-5B.1 y CI-5C se superponen. Sus cantidades se conservan por etapa. CI-5C combinó E2E por socket Uvicorn/FastAPI con integraciones ASGI y PostgreSQL real. Las verificaciones criptográficas usaron JWT firmados localmente y JWKS controlados. Los fallos se indujeron con triggers SQL en un desechable. Las operaciones de juego posteriores a la apertura se simularon en SQL y no representan endpoints implementados.

- **Desechables**: PostgreSQL 16.15 en `127.0.0.1:25483`, MongoDB 7.0.45 en `127.0.0.1:37083`. Se autenticaron usuarios de aplicación y migración, y se comprobaron Settings y drivers antes de cada suite. Se bloquearon `5432`, `27017`, `15433` y `27029`. CI-5C usó `014` y CI-5B.1 separó las revisiones históricas exigidas por sus fixtures.
- **Persistente aislado en CI-5D**: `127.0.0.1:15433/pokearena_alembic_frontend_dev` (`orm_media_test`, `014`) y `127.0.0.1:27029/pokearena_catalog_frontend_dev` (`media_test` y `projection_test`). Se validaron destinos efectivos, ACL y transacciones SQL de solo lectura. Los comandos Mongo observados fueron de lectura o gestión de sesión. Las huellas de las lecturas antes y después coincidieron.

Desde la raíz, los siguientes comandos documentan el alcance. Las pruebas necesitan las URLs técnicas de desechables, su revisión aplicable y un bloqueo de los cuatro puertos protegidos. El dry-run requiere el par aislado verificado y credenciales técnicas inyectadas de forma privada.

```sh
(cd backend && .venv/bin/python -B -m alembic heads)
(cd backend && .venv/bin/python -B -m pytest -q -ra -p no:cacheprovider \
  tests/test_initial_collection_postgresql.py tests/test_initial_pack_http.py)
(cd backend && .venv/bin/python -B -m pytest -q -ra -p no:cacheprovider \
  tests/test_identity_google_login.py)
(cd backend && .venv/bin/python -B -m pytest -q -ra -p no:cacheprovider \
  tests/test_web_create_card.py -k 'test_google_rechaza or test_oidc_no_registra')
backend/.venv/bin/python -B backend/seed_cartas_ci4.py --dry-run --seed 2026 --lote CI4-2026
git diff --check
```

## Conciliación persistente y respaldos

| Componente | Lote CI4-2026 | Catálogo completo |
|---|---:|---:|
| Cartas SQL | 80, 20 de cada rareza | 82 |
| Imágenes SQL READY | 80 | 82 |
| Objetos GridFS verificados | 160 | 164 |
| Eventos CardCreated PROCESSED | 80 | 82 |
| Proyecciones MongoDB | 80 | 82 |
| Comunes elegibles según el filtro SQL real | 20 | 20 |

El dry-run terminó con 80 existentes, cero pendientes y cero fallidas. Las claves de idempotencia, huellas, respuestas `201` y contadores conciliaron. Las cartas previas `PKA-AGU-001` y `PKA-FUE-001` son raras. El manifiesto ordenado por código cubre IDs, referencias, claves de idempotencia, versiones y hashes de ambos binarios. **SHA-256** `ac2c5847d7ab4029e5559f0871ddc21db6e95ec3a12fb63d1ebe58f2aad1b7c5`.

En CI-5E se verificó la legibilidad de `postgres.dump` y `postgres_pre_seed_20261109_031626.dump`. Las copias SQL son idénticas byte a byte. `pg_restore --list` reconoció la base aislada y 105 entradas. La extracción completa a salida descartada se efectuó sin destino de base. Los archivos Mongo superaron la lectura gzip y la decodificación BSON o JSON. La instantánea previa contiene dos cartas SQL, cuatro archivos y cuatro chunks de GridFS, una proyección y dos eventos. La proyección faltante corresponde al evento que estaba `PENDING`. Esa diferencia histórica coincide con la publicación eventual y ambas cartas quedaron conciliadas en CI-5D.

Los respaldos y la documentación identifican el par aislado. El código del seed valida ese par y rechaza los puertos originales. La revisión no encontró una traza operacional contemporánea suficiente para acreditar por separado la ausencia de escrituras del seed histórico en ambos motores originales. CI-5D y CI-5E no conectaron a ellos. No se restauraron respaldos.

## Arquitectura, calidad y observaciones

La composición FastAPI conecta Identidad, Jugadores y Catálogo. El adaptador OIDC se limita a verificar la credencial. Los servicios de colección orquestan sus invariantes mediante un puerto de unidad de trabajo y el adaptador SQL controla los bloqueos y escrituras. La provisión y la apertura usan PostgreSQL, mientras GridFS y la proyección pertenecen a Catálogo. CI-5B.1 reutilizó la validación del paquete cerrado y dejó la autorización posterior ligada a la marca durable. La sanitización OIDC, las guardas de destinos de Outbox y la corrección AST quedaron cubiertas por regresión.

| Nivel | Observación y efecto |
|---|---|
| Medio, operación local | `manage.py setup-dev` conserva valores fijos preexistentes y apunta a los contenedores locales de los puertos originales. Queda excluido de la integración auditada. Revisar por separado su configuración y la vigencia de esos valores antes de usarlo en un entorno compartido. |
| Medio, custodia de respaldos | Los respaldos CI-4 inspeccionados tienen modo `0644` y los directorios revisados `0755`. El acceso efectivo depende de los permisos de toda la ruta. Revisar custodia y permisos de forma separada. |
| Bajo, trazabilidad | Falta evidencia operacional contemporánea suficiente sobre los motores originales durante el seed histórico. Conservar este límite al publicar el informe. |
| Bajo, calidad | Python compiló 97 archivos rastreados. Ruff 0.17.4 reportó 16 diagnósticos preexistentes de formato e imports y manejo de excepciones. Mypy 2.4.1 reportó tres reexportaciones de `http_module` ya presentes en la base. El diff histórico acumulado reporta 24 avisos de espacios finales en contratos. El diff documental local pasa `git diff --check`. |

No se detectaron bloqueos funcionales o de integridad para el onboarding validado. La auditoría no modifica datos, roles, secretos, migraciones ni frontend. Las pruebas con escritura se limitaron a los desechables. El cierre no repitió el seed, no arrancó workers y no realizó commit ni push.

## Preparación para React

1. Intercambiar el ID token de Google por el Bearer opaco de Poké-Arena en una de las dos rutas de login. Usar el rol persistido de la respuesta para separar los flujos de jugador y administrador. Evitar registrar cualquiera de los tokens.
2. Consultar `GET /api/v1/player/initial-pack` para PLAYER. En `PENDING_CATALOG`, mostrar la espera y explicar que un ingreso posterior reintenta la provisión. Consultar GET repetidamente no otorga el premio.
3. En `READY_TO_OPEN`, renderizar las 15 cartas que devuelve el servidor con `id`, `code` y `name`. Mantener esos datos mientras se confirma con `POST /api/v1/player/initial-pack/open` sin cuerpo o con `{}`. `COMPLETED` conserva `opened_at` y devuelve `cards: []`. El paquete no devuelve URLs de imagen ni un inventario general.
4. Tratar `401` como sesión inválida, `403` como falta de acceso y diferenciar los `409` por su código de problema. Permitir reintento ante `503` sin duplicar transiciones locales. Consumir el estado confirmado por el backend al recargar.
5. La integración visual, la validación de un PLAYER con Google real y cualquier consumo productivo del guard requieren trabajo autorizado por separado. Los mazos, el juego, la exploración y la colección visual completa siguen fuera de este cierre.
