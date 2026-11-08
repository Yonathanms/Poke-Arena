# Entrega 1B.2A — ORM y persistencia PostgreSQL

Fecha: 2026-11-06. Alcance: representar el esquema 008 y preparar persistencia,
sin modificar fuentes ni implementar Crear carta completo. 1B.2B no autorizada.

## Resultado y correspondencia

| Modelo | Tabla física | Propietario |
|---|---|---|
| `CartaORM` | `catalog_cards` | `gestion-cartas/adapters/cartas_orm.py` |
| `HabilidadORM` | `catalog_abilities` | Mismo adaptador; solo consulta de habilidades por puerto |
| `ImagenCartaORM` | `catalog_card_images` | Mismo adaptador; autoridad SQL, sin binarios |
| `ContadorCartaORM` | `catalog_card_code_counters` | Mismo adaptador; PK natural `card_type` |
| `IdempotencyRecordORM` | `shared_idempotency_records` | `shared/idempotencia/models.py` |
| `OutboxEventORM` | `shared_outbox` | `shared/outbox.py`, separado del worker |

Las entidades conservan IDs VARCHAR(36), no UUID SQL ni BIGINT. `version` de
carta sí es BIGINT. Se conservaron nombres, tamaños, nulabilidad, defaults del
servidor, CHECK, índices, UNIQUE y FK; incluido `catalog_cards_pkey1`, nombre
histórico originado por la tabla legada que conserva `catalog_cards_pkey`.
No se agregaron defaults Python para IDs/fechas ni columnas anticipadas.

Relaciones: carta → habilidad obligatoria reutilizable; carta → imagen opcional
y única, y habilidad → carta destino de evolución opcional. Las tres FK del
catálogo son `ON DELETE RESTRICT`, sin cascada de borrado ORM. La cuarta FK
del esquema completo pertenece a identidad (`identity_sessions.user_id`) y
usa `ON DELETE CASCADE`. La FK circular del catálogo se desambigua con
`foreign_keys`; no se convierte en diferible ni se inventa otra relación SQL.
Se exige carga explícita (`lazy="raise"`, pruebas con `selectinload`), evitando
consultas implícitas al acceder a atributos asíncronos. Una FK no acredita bytes
reales ni publicación para jugadores.

Se conserva la semántica SQL existente: imagen mínima 300x420 con tolerancia de
008, `image_id` nullable por 007, estados Outbox sin un CHECK nuevo y `attempts`
Outbox sin default desde 004. El cuerpo de respuesta idempotente usa
`JSONB(none_as_null=True)` para distinguir ausencia SQL de un valor JSON null y
respetar el CHECK de pares. No se reinterpreta `params` de habilidades.

## Decisión arquitectónica aprobada: imports y registro

El usuario aprobó conservar los directorios oficiales con guiones, centralizar
`importlib.import_module()` en composición y usar imports relativos internos.
`catalogo_module.py` concentra esa carga y expone dominio, puertos,
`modelos_persistencia()` y `crear_repositorio_cartas(session)`. No modifica
`sys.path`, registra rutas HTTP ni arranca clientes/procesos. No existen llamadas
a importlib en servicios, repositorios o dominio.

Motivo: conservar el árbol oficial sin imports sintácticamente inválidos ni
alias duplicados de los paquetes. Importar repetidamente la composición reutiliza
las mismas clases en el caché estándar de módulos. No usar `reload` de mapeos.
Limitación: IDEs, analizadores estáticos y herramientas que exijan nombres de
paquete convencionales no pueden seguir completamente la frontera dinámica.
La fábrica de la fachada declara `Any` en su retorno dinámico. Mypy analiza el
puerto y el adaptador con sus nombres completos de módulo, lo que conserva el
contexto de los imports relativos y permite comprobar sus firmas. La prueba de
composición verifica que la instancia usa el puerto canónico. Las pruebas
también verifican imports, composición, dependencias
y seis clases registradas una sola vez. Ampliaciones de otros módulos deberán
usar sus puntos de composición y conservar esta disciplina.

`database/postgresql/base.py` contiene exclusivamente el registro declarativo,
sin tablas, configuración ni engine. `connection.py` lo importa/reexporta para
preservar compatibilidad. Todos los mapeos comparten esa misma `Base`; importar
solo la composición no exige URLs ni configura el runtime. Los modelos
compartidos no pertenecen al catálogo: este los incorpora al conjunto de registro
pero no los redefine. Las notas antiguas que situaban ORM en dominio se corrigieron
por la autorización explícita actual; no se reorganizaron carpetas.

Referencias primarias consultadas: [importlib de Python](https://docs.python.org/3/library/importlib.html#importlib.import_module)
y [sesiones e I/O explícito de SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).

## Contratos de persistencia y transacciones

`Carta` y `Habilidad` son representaciones puras en `domain/carta_model.py`;
no son DTO HTTP ni clases ORM. No incluyen todavía fábrica de creación,
validación completa de negocio, interpretación de efectos o procesamiento.

`CartasRepositoryPort` define consulta por ID/código, lectura de habilidad por
código, inserción y lectura bloqueante de contador. `SqlCartaRepository` recibe
una AsyncSession, retorna estados puros y copia el JSON de habilidades.
`agregar()` hace flush y puede afectar el conjunto pendiente de la unidad de
trabajo de esa sesión; no confirma ni coordina el caso de uso. La lectura
`FOR UPDATE` mantiene el bloqueo hasta terminar la transacción; no incrementa,
reserva, reinicia ni crea contadores. El asignador futuro sigue pendiente.

Todas las operaciones exigen una transacción raíz activa abierta con `begin()`.
El adaptador consulta `sync_session.get_transaction().origin` mediante la API
pública de SQLAlchemy 2 y rechaza `AUTOBEGIN`, incluso si una consulta previa
ya abrió una transacción. Un savepoint dentro de un `BEGIN` explícito sigue
siendo válido. El llamador es dueño
de commit/rollback/cierre. Para una sesión obtenida de `get_db()`, usar
`async with session.begin()`. Para un bloque autónomo, la nueva utilidad
`transactional_session()` de la conexión oficial abre/cierra sesión y transacción:
commit al salir normalmente; rollback ante excepción. No anidar ambas formas ni
compartir una sesión entre tareas concurrentes. La utilidad acepta una fábrica
inyectada para pruebas, sin crear motores en repositorios.

Los fallos DBAPI se traducen a `ErrorPersistencia`: duplicado, referencia,
restricción u operación. Solo se conservan categoría y nombre de constraint;
no se incluyen SQL, valores ni detalles del driver en el mensaje y se suprime
su cadena de presentación. La excepción original no debe registrarse por
inspección interna. Tras fallo de escritura se debe salir/revertir la unidad
completa antes de reutilizar la sesión. La traducción a errores de dominio/HTTP
queda para la etapa del caso de uso.

## Archivos

Nuevos, dentro de las carpetas existentes:

- `backend/src/database/postgresql/base.py`.
- `backend/src/modules/catalogo/gestion-cartas/adapters/cartas_orm.py`.
- `backend/src/shared/idempotencia/models.py`.
- `backend/src/shared/outbox.py`.
- `backend/tests/test_card_persistence.py`.
- `backend/docs/contracts/ORM_PERSISTENCE_1B2A.md` (este informe/decisión).

Modificados:

- `backend/src/database/postgresql/connection.py`: Base única y límite transaccional.
- `backend/src/modules/catalogo/catalogo_module.py`: composición aprobada.
- `backend/src/modules/catalogo/gestion-cartas/domain/carta_model.py`.
- `backend/src/modules/catalogo/gestion-cartas/ports/cartas_ports.py`.
- `backend/src/modules/catalogo/gestion-cartas/adapters/sql_carta_repository.py`.
- `AGENTS.md`, `README.md`, `ESTRUCTURA-REPOSITORIO.md`.
- `backend/docs/contracts/CARD_CREATION_BACKEND.md` (conserva versión 1.3).
- `backend/src/modules/nota-diseño.txt`, `backend/src/database/explicacion_database.txt`:
  aclaración de dominio puro/ORM sin alterar el árbol oficial.

Sin cambios en las ocho revisiones, env.py, manifiesto histórico, modelos de otras
features, servicios/controladores, frontend, Compose o configuración de secretos.

## Aislamiento y pruebas ejecutadas

Se creó `pokearena-1b2a-20261106` con la misma imagen local PostgreSQL 16 que la
fuente, red propia del mismo nombre, volumen nuevo `pokearena_1b2a_20261106` y
puerto aleatorio exclusivamente loopback. No monta volúmenes originales.
El bootstrap administrativo creó bases nuevas y un migrador aislado no
administrativo; las migraciones y pruebas usan este último. No se modificaron
roles originales. Se conservan las bases de las ejecuciones previas.

Suite final sobre tres bases independientes: `pokearena_alembic_1b2a_orm_final`
preparada con 001–008 y otras dos vacías `pokearena_alembic_1b2a_history_c/d`
para la reconstrucción histórica doble desde raíz/backend. La integración ORM
reutiliza engine/fábrica oficiales con configuración de prueba; no consume la
URL de API como fallback y valida destino/revisión/rol antes de DML.

**Resultado final: 58 passed en 2.22 s; cero omisiones.** Incluye ocho pruebas de
infraestructura, 16 de recuperación Alembic y 34 de composición/persistencia.

- Columnas en orden físico, tipos/tamaños, nulabilidad, defaults, PK, UNIQUE,
  las tres FK mapeadas, nombres de CHECK e índices explícitos comparados por Inspector.
- Expresiones CHECK ORM contrastadas con los cuerpos upgrade de las migraciones
  originales, tomando las sustituciones hasta 008 y excluyendo downgrade.
- Esquema completo de fuente y reconstrucción comparado con el normalizador
  verificado de 1B.1: 12 tablas y cero diferencias estructurales. Metadata de seis
  tablas contrastada también directamente contra la fuente en modo READ ONLY.
- Consultas existentes/ausentes, inserción, límites inclusivos costo/poder/código,
  rechazos, habilidad obligatoria, imagen opcional/única y evolución por FK.
- Unicidad y trigger de código inmutable, restricciones de imágenes y de seed,
  idempotencia por scope/pares SQL NULL y Outbox por agregado/versión e intentos.
- Propiedad transaccional, visibilidad entre sesiones, commit, rollback conjunto
  de carta/contador y bloqueo entre dos sesiones, sin probar aún el asignador.
- Carga sin configuración runtime, dominio/puertos sin infraestructura y registro
  único de modelos compartidos. Ocho hashes históricos siguen intactos.

La prueba explícita de commit conserva una fila sintética en la base aislada;
las demás escrituras se revierten. No se limpiaron tablas para repetir la suite.
Las pruebas requieren destinos nuevos; no apuntarlas a fuentes ni reutilizar
una base con datos de otra ejecución. Sin URLs opt-in: 27 passed, 31 skipped
(integraciones omitidas explícitamente), sin exigir credenciales privadas.

Huellas SHA-256 de dumps lógicos sin propietarios/ACL de las cuatro bases SQL
originales, IDs/imágenes/tiempos de inicio/montajes de los dos contenedores:
iguales antes/después. Los dumps se procesaron en memoria, no se versionan.
Esta comprobación no acredita un respaldo nuevo, failover ni huellas de documentos
Mongo; esta entrega no realiza I/O Mongo. Ambos servicios originales siguen
saludables. La instancia aislada se detiene al cierre y conserva volumen/red.

Comandos de esta ejecución, desde raíz salvo indicación:

```bash
# Provisión/runner privados: reciben secretos en archivos ignorados, no en argv.
backend/.venv/bin/python docker-data/validation/1b2a-20261106/prepare.py
backend/.venv/bin/python docker-data/validation/1b2a-20261106/prepare_final.py
backend/.venv/bin/python docker-data/validation/1b2a-20261106/run_tests.py backend/tests
# Comparación desde backend:
.venv/bin/python -c "import runpy; runpy.run_path('../docker-data/validation/1b2a-20261106/verify.py')"
# Suite local sin URLs opt-in:
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q
git diff --check
docker stop pokearena-1b2a-20261106
```

La provisión privada conserva argumentos Docker/psql exactos; crea recursos
nuevos y no es una CLI estable para clones. No reejecutarla sobre nombres
existentes. Evidencia, URLs privadas y logs en
`docker-data/validation/1b2a-20261106/`, ignorado por Git. Las URLs no aparecen
en documentación ni logs públicos. Ruff/Mypy no instalados: no se afirma haberlos
ejecutado. Se revisan compilación, docstrings, longitud de líneas nuevas,
diff y ausencia de secretos además de pytest.

## Corrección del Code Review de 1B.2A

| Hallazgo | Corrección y verificación |
|---|---|
| `AUTOBEGIN` aceptado | El adaptador exige `SessionTransactionOrigin.BEGIN` en la transacción raíz activa. Las cinco operaciones rechazan una transacción implícita, conservan su propietario y permiten un `BEGIN` posterior al rollback. |
| Falso positivo del bloqueo | Tres conexiones independientes comprueban en PostgreSQL que el PID de la primera bloquea al de la segunda. La segunda continúa tras liberar el bloqueo y los seis contadores conservan sus valores. Una prueba adicional verifica `55P03` bajo `lock_timeout` y la recuperación tras rollback. |
| Tipado estricto | `manage.py lint` pasa los nombres completos de módulo a Mypy con el `pyproject.toml` existente. Se corrigieron el SQLSTATE opcional y los tipos de reflexión en pruebas. `Any` queda explícito en el retorno de composición dinámica. |
| Defaults textuales | Se normalizan los casts escalares previstos y se conservan las mayúsculas y el contenido del literal. |
| Cantidad de FK | Se distinguen tres FK del catálogo y cuatro del esquema completo. |
| Errores de lectura y bloqueo | Pruebas del adaptador cubren las consultas y la traducción de códigos conocidos, desconocidos o ausentes. El mensaje público excluye SQL y valores del driver. |
| Imports Ruff | Se ordenaron los cuatro bloques señalados. |

La corrección se validó con PostgreSQL 16 en un contenedor efímero. Se copió
el clúster aislado detenido a un `tmpfs` independiente y se crearon dos bases
desde una plantilla ya en 008, una para la suite y otra para los controles
negativos. El contenedor y sus datos temporales se retiraron al finalizar.
La prueba histórica que reconstruye bases con Alembic se omitió deliberadamente.

- **Pytest:** 84 aprobadas y una omitida. Las integraciones ORM se ejecutaron.
- **Regresión:** tres controles negativos fallaron por las razones previstas al
  reintroducir el guard anterior, sustituir el bloqueo por una demora y volver
  a igualar `PENDING` con `pending`.
- **Ruff:** backend y ambos archivos de pruebas afectados aprobados. La CLI
  raíz conserva tres diagnósticos preexistentes fuera de la corrección.
- **Mypy:** 22 módulos de producción y los dos archivos de pruebas afectados
  aprobados con configuración estricta. La referencia `HEAD` previa a 1B.2A
  aprobó sus 18 módulos mediante el mismo método.
- **Coverage:** 99 % en los nueve módulos de producción de 1B.2A. Quedaron
  fuera dos sentencias de `get_db()`. Las declaraciones ORM cuentan como
  ejecutadas al importar, por lo que el porcentaje es una métrica auxiliar.

El comando de lint es `backend/.venv/bin/python manage.py lint`. Para esta
validación se reutilizaron Ruff, Mypy y coverage en un directorio temporal
fuera del repositorio. La prueba ORM usa `ORM_TEST_DATABASE_URL` hacia una
copia aislada en 008. Mantener `ALEMBIC_TEST_URL_A/B` sin definir en una
validación que excluya migraciones.

## Diferencias y pendientes

No se detectaron diferencias ORM/SQL en las seis tablas representadas.
Los CHECK preservan expresiones históricas, incluida su semántica NULL;
representar el esquema no corrige sus limitaciones. El trigger se conserva
mediante Alembic, no se recrea con DDL ORM.

La metadata solo representa seis de las doce tablas; las restantes pertenecen a
otras responsabilidades o al legado. `env.py` permanece intacto con
`target_metadata=None` y autogenerate bloqueado. No ejecutar `create_all`,
stamp, downgrade ni sucesoras con esta representación parcial.

Para una futura 1B.2B autorizada: evaluar datos antes de resolver las dimensiones
flexibles de 008 frente al requisito 600x840/5:7, política histórica, semántica
de CHECK nullable si se propone reforzarla y cualquier necesidad real de esquema.
No hay propuesta de migración aplicada ni permiso implícito para modificarla.
Referencias/bucket GridFS, recuperación/idempotencia completa, asignación de
códigos, publicación/proyección, efectos/ciclos y casos de uso siguen pendientes
de sus decisiones y fases. No activar workers.

## Estado de Git

La entrega y sus correcciones siguen en el árbol de trabajo, sin staging, commit
ni push. El parche local `backend/cambios_pendientes_1B2A.patch` permanece aparte
de los archivos de entrega. Las evidencias, credenciales y volúmenes quedan
fuera del seguimiento.
