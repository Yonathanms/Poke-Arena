# Poké-Arena – Plataforma de Cartas Coleccionables

Repositorio del proyecto para el curso **CE-116: Diseño y Calidad en Productos Tecnológicos** (ITCR).  
Equipo de Desarrollo: **MAFY**

---

## Requisitos Previos

Antes de comenzar, asegúrate de tener instalado en tu máquina:
1. **Git:** ([Descargar Git](https://git-scm.com/))
2. **Docker Desktop:** Debe estar iniciado y corriendo ([Descargar Docker Desktop](https://www.docker.com/products/docker-desktop/))
3. **Python 3.11 o superior:** Con `pip` habilitado en las variables de entorno ([Descargar Python](https://www.python.org/downloads/))
4. **Node.js (v18 o v20 LTS):** Con `npm` ([Descargar Node.js](https://nodejs.org/))

---

## Instalación y Puesta en Marcha (Paso a Paso)

Todos los comandos iniciales se ejecutan desde la **raíz del proyecto** (`Poke-Arena/`).

### Paso 1: Configurar el entorno e instalar dependencias
Abre una terminal en la raíz del proyecto y ejecuta:

```powershell
# Ubicación: Poke-Arena/
python manage.py install
```

Este comando automatiza todo:
* Genera tu archivo local `.env` a partir de `.env.example` (si no existía).
* Crea el entorno virtual de Python (`backend/.venv`) e instala los paquetes necesarios.
* Descarga e instala los paquetes de Node.js en `frontend/`.

*(Si en algún momento solo quieres regenerar el archivo de configuración sin reinstalar librerías, puedes ejecutar: `python manage.py env`).*

---

### Paso 2: Iniciar las Bases de Datos en Docker
Desde la raíz del proyecto, enciende los motores de persistencia (**PostgreSQL en `:5432`** y **MongoDB en `:27017`**) en segundo plano:

```powershell
# Ubicación: Poke-Arena/
python manage.py dbs
```
*(Equivalente a ejecutar `docker compose up -d`).*

> **Nota importante:** Docker se utiliza exclusivamente para levantar los servidores de bases de datos. El código del backend y del frontend se corre directamente en local.

---

## Flujo de Trabajo Diario (Dividir Terminales en VS Code)

Para desarrollar cómodamente con recarga automática (*hot-reload*), abre **dos terminales** en VS Code:

### Terminal 1: Backend (FastAPI)
Navega a la carpeta del backend, activa el entorno virtual y levanta el servidor de la API:

```powershell
# Ubicación de la terminal: Poke-Arena\backend
cd backend
.venv\Scripts\activate
uvicorn src.main:app --reload --port 8000
```
*(Atajo alternativo desde la raíz: `python manage.py dev-backend`)*

* Documentación Swagger interactiva: http://localhost:8000/docs
* Verificación de salud (Healthcheck): http://localhost:8000/api/v1/health

---

### Terminal 2: Frontend (React + Vite)
Navega a la carpeta del frontend y ejecuta el servidor de desarrollo:

```powershell
# Ubicación de la terminal: Poke-Arena\frontend
cd frontend
npm run dev
```
*(Atajo alternativo desde la raíz: `python manage.py dev-frontend`)*

* Aplicación Web en vivo: http://localhost:5173

---

## Comandos de Utilidad (`manage.py`)

Todos estos comandos se ejecutan desde la raíz del proyecto (`Poke-Arena/`):

| Comando | Descripción |
| :--- | :--- |
| **`python manage.py install`** | Genera el `.env` e instala dependencias de Backend y Frontend. |
| **`python manage.py env`** | Genera exclusivamente el archivo `.env` a partir de `.env.example`. |
| **`python manage.py dbs`** | Enciende PostgreSQL y MongoDB en Docker. |
| **`python manage.py stop`** | Detiene los contenedores de Docker conservando los datos guardados. |
| **`python manage.py clean`** | Detiene y BORRA los datos de las bases de datos (Reset total). |
| **`python manage.py status`** | Consulta el estado y puertos de los contenedores Docker. |
| **`python manage.py lint`** | Verifica estilo y tipado estricto con Ruff y Mypy. |
| **`python manage.py dev-backend`** | Atajo para arrancar FastAPI en `:8000`. |
| **`python manage.py dev-frontend`** | Atajo para arrancar React / Vite en `:5173`. |

---

## Estructura del Repositorio

>

```text
Poke-Arena/
├── docker-compose.yml              # Bases de datos: PostgreSQL (:5432) y MongoDB (:27017)
├── manage.py                       # CLI para automatizar tareas del equipo
├── .env.example                    # Plantilla oficial de variables de entorno
│
├── frontend/                       # APLICACIÓN WEB (React + TypeScript + Tailwind)
│   └── src/
│       ├── 📁 web-admin/           # Portal de Administradores (Gestión de Catálogo)
│       ├── 📁 web-player/          # Portal de Jugadores (Colección y Partidas)
│       └── 📁 portal-b2b/          # Portal de Organizaciones B2B (Torneos)
│
└── backend/                        # API REST (FastAPI + SQLAlchemy + MongoDB)
    ├── alembic/                    # Historial de versiones y migraciones de PostgreSQL
    └── src/
        ├── main.py                 # Punto de entrada de FastAPI y rutas
        ├── database/               # Conexiones físicas a PostgreSQL, MongoDB y outbox_worker
        ├── shared/                 # Capa Transversal (Configuración .env, roles, errores RFC 7807)
        └── modules/                # LÓGICA DE NEGOCIO Y DOMINIO (Capa 3 de la Arquitectura)
            ├── 📁 catalogo/        # Gestión de cartas y ubicaciones
            ├── 📁 identidad/       # Cuentas, sesiones y autenticación
            ├── 📁 jugadores/       # Colecciones, perfiles, mazos e inventario
            ├── 📁 torneos/         # Gestión de torneos B2B y llaves de API
            └── 📁 motor-juego/     # Motor de batalla puro y máquina de estados
```

> **Regla de oro para crear código nuevo:**  
> Cada submódulo (ejemplo: `catalogo/gestion-cartas`) contiene 5 carpetas de arquitectura hexagonal:
> 1. `controllers/`: Endpoints HTTP y validación con Pydantic DTOs.
> 2. `services/`: Reglas del negocio y casos de uso.
> 3. `domain/`: Modelos de la base de datos (tablas).
> 4. `ports/`: Interfaces abstractas (contratos).
> 5. `adapters/`: Repositorios concretos de PostgreSQL o MongoDB y adaptadores externos.
