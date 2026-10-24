# ADR-002 — Procesamiento durable de imágenes de Crear Carta

Fecha: 2026-10-23.

Estado: decisión técnica registrada por delegación explícita del usuario para preparar la implementación de US 2.1.1 en Sprint 1. No acredita implementación ni pruebas ejecutadas.

## Contexto y fuentes

[US 2.1.1](../../DocsE/pokearena_user_stories_v3_3.csv) exige original válido, miniatura 200 × 280, disponibilidad solo con ambas imágenes, reintentos y estado visible ante fallo. Permite elegir procesamiento síncrono o asíncrono mediante ADR.

El [contrato](../../DocsE/contrato.md) fija Pillow, volumen persistente local/Azure Blob, Unit of Work con rollback, PostgreSQL como fuente de verdad y Transactional Outbox. El [ADR-001](<../../DocsE/Estructuras/Seleccion de Arquitectura de Referencia.md>) fija la arquitectura de referencia usada por el equipo.

## Decisión

Elegir procesamiento **asíncrono durable** de la miniatura. La validación del original es síncrona y ocurre antes de aceptar la creación. El original válido debe estar almacenado de forma durable antes del commit que crea la carta pendiente.

`POST /api/v1/content/cards` responde 201 con identificador, código generado y `image_status=PENDING` una vez confirmada esa transacción. La carta existe como contenido administrativo pendiente, pero no está disponible para jugadores. La respuesta incluye un enlace a su estado. El procesador completa la miniatura y marca `READY` en otro UoW.

Esta decisión aprovecha los estados/reintentos exigidos por la historia y no mantiene transacciones SQL abiertas durante operaciones Pillow o de archivos. No se añade un broker ni un framework. El procesador es otro punto de ejecución del mismo monolito, con trabajo en PostgreSQL.

## Interpretación de rollback

`PENDING`, `PROCESSING`, `RETRY_PENDING` y `FAILED` son estados administrativos válidos y no disponibles. Una referencia incompleta no se presenta como carta lista.

El rollback del contrato se aplica a cada UoW. Si falla el paso que debe confirmar miniatura y disponibilidad, ese UoW se revierte. Después, otro UoW registra el fallo y programa el reintento sobre la carta pendiente ya existente. No se mantiene un commit parcial del paso fallido ni se pretende revertir una transacción anterior ya confirmada.

Una imagen original inválida se rechaza sin crear carta, consumir código ni registrar éxito idempotente. Un fallo al almacenar el original también impide aceptar la creación. Los archivos guardados fuera de SQL se compensan o concilian, pues el rollback SQL no los elimina.

## Política concreta

| Parámetro | Decisión |
| --- | --- |
| Límite del original | 5.000.000 bytes; «MB» decimal. |
| Formatos originales | PNG, JPEG/JPG y WebP, comprobados por decodificación. |
| Proporción | Exacta: ancho × 7 = alto × 5, sin tolerancia arbitraria. |
| Resolución mínima | 600 × 840 píxeles. |
| Original | Conservar bytes aceptados; no reducirlo automáticamente. |
| Miniatura | WebP de 200 × 280, redimensionada con Pillow; no recortar la imagen. |
| Intentos automáticos | Cinco en total. El primero empieza al reclamar el trabajo. |
| Espera tras los primeros cuatro fallos | 2, 10, 30 y 120 segundos. |
| Lease | 60 segundos, renovable cada 20 segundos; reloj de PostgreSQL. |
| Recuperación de caída | Reclamar trabajo con lease vencido, respetando límite de intentos. |
| Después del quinto fallo | `FAILED`, conservar original y último error sanitizado; alerta en logs. |
| Recuperación operativa | Reencolar la misma carta mediante `RetryCardImagesUseCase`; nuevo ciclo de procesamiento, sin otro código ni carta. |

Estos valores son configuración técnica inicial, no requisitos atribuidos al enunciado. Pueden ajustarse operativamente manteniendo las invariantes y documentando el cambio. El procesamiento CPU de Pillow no debe bloquear el event loop HTTP.

La recuperación operativa se expone como comando administrativo del sistema, por ejemplo un futuro `manage.py retry-card-images --card-id ...`, bajo acceso de operador. No se añade un endpoint genérico de edición ni una nueva funcionalidad de juego. El comando todavía no existe.

Los formatos con múltiples frames se validan completos y la miniatura se genera a partir del primer frame. El original se conserva. Se verifica la proporción sobre las dimensiones del raster que se muestra; si se aplica orientación EXIF, la validación y miniatura deben usar la misma orientación. Se prueban ambas situaciones para evitar aceptar una imagen y renderizar otra geometría.

## Concurrencia y consistencia de archivos

1. Usar claves de almacenamiento propias del sistema; nunca rutas proporcionadas por el cliente.
2. El original tiene una clave inmutable referenciada por SQL. Las miniaturas de cada intento incluyen su token de reclamación.
3. Reclamar trabajo con transacción corta y token/lease; hacer I/O fuera de ella.
4. La finalización comprueba token de reclamación y estado/versión en un nuevo UoW. Un trabajador cuyo lease perdió no puede publicar disponibilidad.
5. El commit de finalización referencia la miniatura durable, cambia el estado y agrega un evento de outbox atómicamente.
6. Una miniatura de un intento perdido es candidata a limpieza únicamente si no está referenciada en SQL.
7. Ante resultado incierto de un commit, consultar el primario antes de compensar archivos. No borrar por una excepción genérica de conexión.

Los originales pendientes no se publican como imágenes listas ni se eliminan al agotar reintentos. La limpieza automática solo alcanza archivos no referenciados de más de 24 horas y vuelve a comprobar referencias en el primario. Este plazo es una política técnica de limpieza, no retención de datos de usuario.

## Alternativas consideradas

- Síncrono: simplifica el caso exitoso inmediato, pero alarga la solicitud y sigue necesitando persistencia durable para el reintento exigido por la historia.
- Tarea en memoria posterior a la respuesta: descartada como mecanismo de garantía; una caída podría perder el trabajo.
- Asíncrono durable: elegido; exige estado visible y un procesador recuperable, ya coherentes con la arquitectura de eventos y reintentos documentada.

## Consecuencias y aceptación

El frontend debe mostrar procesamiento y consultar el estado; no debe anunciar que la carta ya está lista al recibir el primer 201. La misma creación puede responder nuevamente con su snapshot inicial idempotente mientras el recurso ya avanzó a `READY`; la consulta de estado devuelve el estado actual.

La publicación a Mongo es independiente del procesamiento de imágenes. Un fallo Mongo no revierte la carta confirmada ni provoca eliminación de imágenes. Debe recuperarse mediante outbox.

Las pruebas deben cubrir validación inicial, cinco intentos, recuperación de lease, trabajador obsoleto, fallo entre archivo y SQL, commit incierto y doble procesamiento. El detalle y la matriz completa están en [Crear Carta](../design/content/create-card.md).
