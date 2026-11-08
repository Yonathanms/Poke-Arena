# Poké-Arena – Manual de Arquitectura y Estructura del Repositorio

Este documento define la estructura oficial del proyecto, su justificación arquitectónica y el flujo detallado de cómo viajan los datos de inicio a fin entre el Frontend y el Backend.

---

## 1. Estructura Oficial del Repositorio

El proyecto implementa una arquitectura de **Monolito Modular Hexagonal (Ports & Adapters)** con **Persistencia Políglota (PostgreSQL + MongoDB)** y división de portales en el Frontend:

```text
Poke-Arena/
├── docker-compose.yml              # Bases de datos en Docker: PostgreSQL (:5432) y MongoDB (:27017)
├── manage.py                       # CLI automatizado de gestión local
├── .env.example                    # Plantilla de variables de entorno
├── .env                            # Variables de entorno locales (ignorado en Git)
│
├── frontend/                       # APLICACIÓN WEB (React 18 + Vite + TypeScript + Tailwind)
│   └── src/
│       ├── shared/                 # Componentes y utilidades compartidas por todos los portales
│       │   ├── components/         # ImageUploader (5:7 y 4:3), botones, alertas, modales
│       │   └── services/           # Cliente HTTP centralizado (Axios/Fetch a :8000/api/v1)
│       │
│       ├── web-admin/              # Portal de Administradores de Contenido
│       │   ├── shared/             # Utilidades específicas del portal admin
│       │   └── modules/
│       │       ├── auth/           # Login y gestión de sesión de Administrador
│       │       └── catalogo/       # MÓDULO FRONTEND: Gestión de Catálogo
│       │           ├── components/ # Componentes atómicos (CardForm, CardPreviewCard)
│       │           ├── hooks/      # Hooks de estado y mutación (useCreateCard)
│       │           ├── screens/    # Vistas completas ensambladas (CreateCardScreen, CatalogListScreen)
│       │           ├── services/   # Llamadas a endpoints de la API (catalog.api.ts)
│       │           └── types/      # Tipado TypeScript (card-admin.types.ts)
│       │
│       ├── web-player/             # Portal de Jugadores
│       │   └── modules/
│       │       ├── coleccion/      # Vista de inventario de cartas y mazos
│       │       └── partidas/       # Tablero de juego y emparejamiento
│       │
│       └── portal-b2b/             # Portal de Organizaciones B2B (Torneos y Métricas)
│           └── modules/
│               └── torneos/        # Gestión de torneos B2B y llaves de API
│
└── backend/                        # API REST (Python 3.12 + FastAPI + SQLAlchemy 2.0 + Motor)
    ├── alembic/                    # Historial y control de versiones de esquemas SQL
    │   └── versions/               # Migraciones de PostgreSQL (.py)
    │
    └── src/
        ├── main.py                 # Entrada de FastAPI, middlewares CORS y ciclo de vida
        │
        ├── shared/                 # CAPA TRANSVERSAL (Cross-cutting concerns)
        │   ├── config.py           # Variables de entorno y configuración centralizada
        │   ├── seguridad-roles/    # Extracción de JWT, Bearer tokens y RBAC (401 vs 403)
        │   ├── observabilidad/     # Middleware de correlación (X-Correlation-ID) y logs JSON
        │   ├── errores-rfc7807/    # Manejo estándar de excepciones (RFC 7807 Problem Details)
        │   ├── idempotencia/       # Manejo de cabecera Idempotency-Key
        │   └── validacion/         # Esquemas y validadores comunes de Pydantic
        │
        ├── database/               # CAPA DE PERSISTENCIA TÉCNICA
        │   ├── postgresql/         # Motor SQLAlchemy y función inyectable get_db() (:5432)
        │   ├── mongodb/            # Cliente Motor para MongoDB de catálogo (:27017)
        │   └── outbox_worker.py    # Sincronización asíncrona de PostgreSQL -> MongoDB
        │
        └── modules/                # LÓGICA DE NEGOCIO Y DOMINIO (Capa 3 de la Arquitectura)
            │
            ├── catalogo/           # MÓDULO CATÁLOGO (Cartas y Ubicaciones)
            │   ├── catalogo_module.py
            │   ├── gestion-cartas/
            │   │   ├── controllers/        # Endpoints REST (cartas_controller.py, cartas_dtos.py)
            │   │   ├── services/           # Lógica de negocio (cartas_service.py)
            │   │   ├── domain/             # Entidades puras (carta_model.py)
            │   │   ├── ports/              # Interfaces abstractas (cartas_ports.py)
            │   │   └── adapters/           # Repositorios SQL, Mongo y Medios (sql, mongo, imagen)
            │   └── gestion-ubicaciones/
            │       ├── controllers/
            │       ├── services/
            │       ├── domain/
            │       ├── ports/
            │       └── adapters/
            │
            ├── identidad/          # MÓDULO IDENTIDAD (Autenticación y Sesiones)
            │   └── gestion-sesiones/
            │       ├── controllers/
            │       ├── services/
            │       ├── domain/
            │       ├── ports/
            │       └── adapters/          # Cliente Google OAuth2 / Test Provider local
            │
            ├── jugadores/          # MÓDULO JUGADORES
            │   ├── coleccion-mazos/       # Colección inicial, mazos e inventario
            │   ├── perfil-cuentas/        # Perfil y estadísticas del jugador
            │   ├── emparejamiento/        # Fila clasificatoria
            │   ├── partidas/              # Ciclo de vida de partida
            │   └── historial-clasificacion/
            │
            ├── torneos/            # MÓDULO TORNEOS B2B
            │   ├── partners-llaves-api/   # Organizaciones y API Keys
            │   ├── gestion-torneos/       # Creación, rondas e inscripción
            │   └── despacho-webhooks/     # Notificación de eventos a terceros
            │
            └── motor-juego/        # MÓDULO MOTOR DE JUEGO (Puro y Determinista)
                ├── domain/                # Resolución de turnos y máquina de estados
                │   ├── motor_batalla.py
                │   ├── maquina_estados.py
                │   └── strategies/        # Efectos de habilidades y modificadores
                └── ports/
                    └── motor_ports.py     # Contrato que usan las partidas para llamarlo
```

---

## 2. ¿Por qué el proyecto tiene esta forma? (Justificación de Diseño)

### En el Frontend:
1. **Separación por Portales de Usuario (`web-admin`, `web-player`, `portal-b2b`):**
   Cada actor tiene requerimientos visuales y de permisos completamente distintos. Separarlos evita mezclar componentes de administración con la interfaz de los jugadores.
2. **Estructura Interna de cada Módulo:**
   * **`screens/`**: La vista completa (página). No contiene lógica compleja ni llamadas HTTP directas; su trabajo es **ensamblar** los componentes visuales y conectarlos con el hook.
   * **`components/`**: Bloques visuales reutilizables (el formulario, el selector de imágenes, la tarjeta de previsualización en vivo).
   * **`hooks/`**: Contiene la reactividad de React (`useState`, `useEffect`, validaciones en el cliente y manejo de errores/loading).
   * **`services/`**: Código puro de red (llamadas con `fetch` o `axios` a la API).
   * **`types/`**: Contratos e interfaces de TypeScript para tener auto-completado y cero errores de tipo.
3. **`frontend/src/shared/`**:
   Permite compartir componentes transversales (como el cargador de imágenes configurable a 5:7 o 4:3, botones, alertas y el cliente HTTP base) sin duplicar código entre portales.

### En el Backend:
1. **Arquitectura Hexagonal (Puertos y Adaptadores):**
   El dominio y las reglas de negocio (`domain/`, `services/`) están desacoplados de la tecnología física (`adapters/`). Si el día de mañana se cambia PostgreSQL por otra base de datos, el código de reglas del juego **no cambia en absoluto**.
2. **Capa Transversal (`src/shared/`):**
   Centraliza la seguridad (RBAC), el estándar de errores (RFC 7807), la idempotencia y la observabilidad para que ningún módulo tenga que reinventar cómo loguear o autenticar.
3. **Persistencia Políglota Inteligente (PostgreSQL + MongoDB):**
   * **PostgreSQL:** Transaccional y relacional estricto (ACID) para crear y editar datos con consistencia absoluta.
   * **MongoDB:** Catálogo optimizado en documentos JSON planos para permitir búsquedas ultra rápidas sin JOINs escalables a más de 10.000 cartas.
   * **`outbox_worker.py`:** Garantiza que los cambios en PostgreSQL se repliquen en MongoDB de forma asíncrona sin riesgo de que los datos queden inconsistentes.

---

## 3. Flujo Completo de Extremo a Extremo: "Crear una Carta"

A continuación se detalla el viaje completo de una petición cuando un Administrador crea una nueva carta en el sistema:

```text
[1. Usuario interactúa]
   CreateCardScreen.tsx  <--  CardForm.tsx + CardImageUploader.tsx
            │
            ▼
[2. Reactividad & Estado]
   useCreateCard.ts (Valida inputs en el cliente)
            │
            ▼
[3. Llamada de Red]
   catalog.api.ts  ──( HTTP POST /api/v1/content/cards con FormData )──►
            │
            ▼
[4. Entrada en la API]
   cartas_controller.py  (Valida datos y tipos con cartas_dtos.py)
            │
            ▼
[5. Lógica de Negocio]
   cartas_service.py  (Invariantes del juego + procesa imagen con Pillow a WebP 5:7)
            │
            ▼
[6. Contrato de Puerto]
   cartas_ports.py  (ICartaRepository)
            │
            ▼
[7. Persistencia Transaccional]
   sql_carta_repository.py
      ├── INSERT INTO cartas (...)               (en PostgreSQL :5432)
      └── INSERT INTO outbox (evento="CARTA_CREADA")
            │
            ▼
[8. Respuesta Inmediata al Usuario]
   API retorna HTTP 201 Created con JSON de la carta creada
   Frontend recibe respuesta -> Limpia formulario -> Muestra Toast "Carta Creada"
            │
            ▼  (En segundo plano)
[9. Sincronización NoSQL]
   outbox_worker.py lee evento de PostgreSQL -> Inserta documento en MongoDB (:27017)
```

---

### Desglose paso a paso:

#### Paso 1: Interfaz y Formulario en el Frontend
* El Administrador entra a `CreateCardScreen.tsx`.
* La pantalla renderiza el componente `CardForm.tsx` (para nombre, costo, poder, rareza) y el componente `CardImageUploader.tsx` (que valida que la imagen seleccionada cumpla con el formato y tamaño).
* Mientras el usuario escribe, `CardPreviewCard.tsx` dibuja en tiempo real cómo se verá la carta física.

#### Paso 2: Hook y llamada HTTP
* Al pulsar el botón "Guardar Carta", se dispara la función en el hook `useCreateCard.ts`.
* El hook activa el estado `loading = true`.
* Invoca a `catalog.api.ts`, el cual construye un `FormData` adjuntando los campos y el archivo de imagen, agregando la cabecera `Idempotency-Key` (para evitar duplicados por doble clic).
* Envía la petición por red: `POST http://localhost:8000/api/v1/content/cards`.

#### Paso 3: Recepción en el Controlador de FastAPI
* La petición entra en `cartas_controller.py`.
* Pydantic (`cartas_dtos.py`) valida automáticamente los tipos:
  * Si el costo no es numérico o la rareza es inválida, responde inmediatamente un error **422 Unprocessable Entity** bajo el estándar RFC 7807 sin tocar la base de datos.
  * Si los datos son correctos, el controlador se los pasa a `cartas_service.py`.

#### Paso 4: Lógica de Negocio y Reglas del Juego
* `cartas_service.py` aplica las reglas de dominio:
  1. Verifica que no exista otra carta con el mismo nombre o código.
  2. Valida las invariantes del juego (por ejemplo, que el poder esté dentro del rango permitido para esa rareza).
  3. Llama a `imagen_carta_adapter.py` (con la librería **Pillow**):
     * Valida la relación de aspecto 5:7.
     * Genera la versión oficial WebP de 600x840 px.
     * Genera la miniatura de 200x280 px.
     * Guarda ambos archivos en `./uploads/cartas/`.

#### Paso 5: Persistencia Transaccional ACID en PostgreSQL
* El servicio invoca el puerto `CartaRepositoryPort` implementado por `sql_carta_repository.py`.
* Dentro de una **misma transacción SQL atómica**:
  1. Guarda la fila de la carta con sus rutas de imagen en la tabla `cartas`.
  2. Inserta una fila en la tabla `outbox`:  
     `{ evento: "CARTA_CREADA", payload: { codigo: "PKA-001", nombre: "Pikachu", ... } }`.
  3. Ejecuta `session.commit()`.

#### Paso 6: Respuesta de Éxito al Usuario (Criterio de Aceptación)
* El controlador recibe la carta confirmada y responde al frontend con código **201 Created** y los datos en formato JSON.
* En el frontend, `useCreateCard.ts` recibe el 201, apaga el `loading`, limpia los campos del formulario y le muestra un mensaje de éxito al Administrador.

#### Paso 7: Sincronización hacia MongoDB en Segundo Plano
* De forma asíncrona, `outbox_worker.py` (que corre continuamente):
  1. Lee los eventos no procesados de la tabla `outbox` en PostgreSQL.
  2. Toma la información de la nueva carta y hace un `update_one(..., upsert=True)` en la colección `cards_catalog` de **MongoDB**.
  3. Marca el evento como procesado en PostgreSQL.
* A partir de ese milisegundo, cuando cualquier jugador entre a buscar cartas en el catálogo, la búsqueda se ejecuta sobre **MongoDB** a máxima velocidad sin ralentizar a PostgreSQL.

---

## 4. Guía Rápida para el Desarrollador: "¿Dónde toco si tengo que...?"

| Si necesitas... | ¿En qué carpeta / archivo trabajas? |
| :--- | :--- |
| Agregar un nuevo campo a un formulario web | `frontend/src/web-admin/modules/catalogo/components/CardForm.tsx` |
| Cambiar el llamado HTTP o la URL de un endpoint | `frontend/src/web-admin/modules/catalogo/services/catalog.api.ts` |
| Agregar una nueva ruta o endpoint en el Backend | `backend/src/modules/catalogo/gestion-cartas/controllers/cartas_controller.py` |
| Validar un nuevo campo de entrada en la API | `backend/src/modules/catalogo/gestion-cartas/controllers/cartas_dtos.py` |
| Cambiar una regla de negocio del juego | `backend/src/modules/catalogo/gestion-cartas/services/cartas_service.py` |
| Representar tablas existentes con ORM | `backend/src/modules/catalogo/gestion-cartas/adapters/cartas_orm.py`; cambios SQL solo mediante Alembic autorizado |
| Modificar cómo se procesan o recortan las imágenes | `backend/src/modules/catalogo/gestion-cartas/adapters/imagen_carta_adapter.py` |
| Modificar la consulta SQL en PostgreSQL | `backend/src/modules/catalogo/gestion-cartas/adapters/sql_carta_repository.py` |
| Modificar la proyección o búsqueda en MongoDB | `backend/src/modules/catalogo/gestion-cartas/adapters/mongo_carta_repository.py` |
| Cambiar variables del sistema o puertos | `backend/src/shared/config.py` y `.env` |


### Aclaración aprobada en 1B.2A

El dominio es puro; SQLAlchemy pertenece a adaptadores. La narrativa anterior es un flujo conceptual histórico, no evidencia de endpoints, imágenes o workers implementados. Nombres físicos, límites y decisiones vigentes están en el contrato v1.3. La carga de `gestion-cartas` se centraliza en `catalogo_module.py` con importlib aprobado, sin renombrar carpetas ni modificar sys.path. Véase `backend/docs/contracts/ORM_PERSISTENCE_1B2A.md`.
