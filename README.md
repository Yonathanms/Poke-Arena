# Poké-Arena – Plataforma de Cartas Coleccionables

Repositorio del proyecto del curso **CE-116: Diseño y Calidad en Productos Tecnológicos** (ITCR).  
Equipo de Desarrollo: **MAFY**.

---

##  Inicio Rápido Centralizado (`manage.py`)

Para evitar tener que memorizar comandos largos de Docker o rutas de entornos virtuales, el proyecto cuenta con un **CLI centralizado en Python** (`manage.py`) que funciona de forma idéntica en **Windows, Linux y macOS**:

```bash
# 1. Instalar todas las dependencias del proyecto (Backend y Frontend en un solo paso)
python manage.py install-deps

# 2. Levantar el sistema completo en Docker
python manage.py start-full

# 3. Probar el sistema en tu navegador
#  http://localhost
```

---

##  Panel de Comandos de `manage.py`

| Comando | Qué hace exactamente | Cuándo usarlo |
| :--- | :--- | :--- |
| **`python manage.py install-deps`** | Crea el `.env`, crea el `.venv` en backend, instala las librerías de Python y ejecuta `npm install` en el frontend. | Al clonar el repositorio por primera vez o al actualizar librerías. *(Alias: `install`)* |
| **`python manage.py start-dbs`** | Levanta **ÚNICAMENTE** las bases de datos en Docker (PostgreSQL Master en `:5432`, Réplica en `:5433` y MongoDB en `:27017`). | **Día a día (Desarrollo Rápido):** Cuando estás programando y quieres recarga en caliente instantánea al editar código. *(Alias: `dbs`)* |
| **`python manage.py start-full`** | Levanta el clúster **COMPLETO** en Docker (Bases de datos + 2 réplicas del Backend + Frontend SPA en Nginx + Balanceador de carga en `:80`). | **Evaluación y Entregas:** Para probar la arquitectura completa tal como correrá en producción. *(Alias: `up`)* |
| **`python manage.py stop`** | Apaga y detiene todos los contenedores Docker **CONSERVANDO los datos** guardados en PostgreSQL y MongoDB. | Al terminar tu jornada de trabajo. Tus cartas y partidas guardadas **no se pierden**. *(Alias: `down`)* |
| **`python manage.py stop-clean`** | Detiene los contenedores y **BORRA los volúmenes de datos** (Reset total). | Cuando quieras limpiar por completo las bases de datos y empezar de cero. *(Alias: `clean`)* |
| **`python manage.py status`** | Muestra el estado actual y puertos de todos los contenedores Docker (`Up`, `Healthy`, etc.). | Para verificar rápidamente qué servicios están encendidos. |
| **`python manage.py logs`** | Muestra los registros y logs en vivo de los contenedores (`python manage.py logs backend-1` para uno en específico). | Para depurar errores de comunicación en tiempo real. |
| **`python manage.py test`** | Ejecuta la suite completa de pruebas unitarias y de arquitectura con `pytest`. | Antes de realizar cualquier commit o Pull Request. *(Alias: `run-tests`)* |
| **`python manage.py lint`** | Valida el estilo con `Ruff` y comprueba que no haya errores de tipado estricto con `Mypy`. | Para asegurar que el código cumple con los estándares del curso. *(Alias: `run-lint`)* |
| **`python manage.py smoke-test`** | Ejecuta la prueba de humo de signos vitales (comprueba frontend, healthcheck, Swagger y flujo de cartas). | Para validar que el clúster en Docker está 100% operativo de punta a punta. *(Alias: `smoke`)* |

---

##  Diferencias Clave que Debes Conocer

### 1. `start-dbs` vs. `start-full`: ¿Cuál debo usar?
* **Usa `start-dbs` para PROGRAMAR (Modo Desarrollo Local):**
  * Solo enciende PostgreSQL y MongoDB en Docker.
  * En una terminal ejecutas `uvicorn src.main:app --reload --port 8000` (dentro de `backend/`).
  * En otra terminal ejecutas `npm run dev` (dentro de `frontend/` en `http://localhost:5173`).
  * **Ventaja:** Cualquier cambio que guardes en tu editor se refleja en el navegador al instante sin tener que reconstruir contenedores.
* **Usa `start-full` para EVALUAR (Modo Clúster Completo):**
  * Enciende todo en contenedores: Nginx (`:80`), 2 réplicas del Backend y el Frontend compilado.
  * Abre directamente en **[http://localhost](http://localhost)**.
  * **Ventaja:** Demuestra la arquitectura real balanceada requerida por la cátedra.

### 2. `stop` vs. `stop-clean`: ¿Cuándo se borran los datos?
* **`stop` (Seguro):** Apaga los contenedores pero mantiene el disco virtual (`docker compose down`). Si habías creado cartas o usuarios en la base de datos, seguirán ahí la próxima vez que levantes el sistema.
* **`stop-clean` (Reset):** Apaga los contenedores y destruye los volúmenes (`docker compose down -v`). Úsalo únicamente cuando necesites reiniciar las bases de datos a su estado original vacío.

---

##  Arquitectura del Sistema

El sistema implementa una arquitectura de **Monolito Modular con Diseño Hexagonal (Ports & Adapters)**:
* **Frontend:** React 18, TypeScript (modo estricto `strict: true`), Vite, Tailwind CSS y Lucide Icons.
* **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic, Motor (driver async MongoDB) y Pillow.
* **Bases de Datos & Persistencia Políglota (`RNF-ALM-01`):**
  * **PostgreSQL 16 (Master y Réplica):** Modelo relacional transaccional (ACID). Separación de sesiones de escritura (Master en `:5432`) y lectura (Réplica en `:5433`, `RNF-DIS-02`).
  * **MongoDB 7.0 (`:27017`):** Proyecciones desnormalizadas de lectura ultrarrápida para catálogo y búsquedas sin joins (`US 2.1.2`).
  * **Almacenamiento Local de Imágenes:** Validación estricta de relación de aspecto en servidor (5:7 para cartas y 4:3 para ubicaciones) y conversión a WebP optimizado con miniaturas.
* **Infraestructura & Red:** Nginx como balanceador de carga (`:80`) distribuyendo el tráfico entre instancias del backend (`RNF-REN-03`).
* **Estándar de Errores:** Respuestas uniformes basadas en **RFC 7807 (Problem Details)** y trazabilidad mediante cabecera `X-Correlation-ID`.

---

##  Requisitos de Software Previos

Antes de comenzar, asegúrate de tener instalado:
1. **Git:** ([Descargar Git](https://git-scm.com/)).
2. **Docker Desktop:** Con soporte para Docker Compose v2 ([Descargar Docker Desktop](https://www.docker.com/products/docker-desktop/)).
3. **Node.js:** Versión 18.x o 20.x LTS ([Descargar Node.js](https://nodejs.org/)).
4. **Python:** Versión **3.12.x** ([Descargar Python 3.12](https://www.python.org/downloads/)). *Asegúrate de marcar "Add Python to PATH" en Windows.*

---

##  Pruebas Automatizadas y Calidad

Puedes correr todas las validaciones de calidad con el CLI:

```bash
# 1. Pruebas unitarias y de arquitectura (10/10)
python manage.py test

# 2. Linter (Ruff) y Tipado Estricto (Mypy)
python manage.py lint

# 3. Prueba de humo de signos vitales (End-to-End contra Docker)
python manage.py smoke-test
```

---

##  Estructura del Repositorio

```text
Poke-Arena/
├── manage.py                   # CLI centralizado para gestionar todo el proyecto
├── docker-compose.yml          # Orquestación Docker (perfiles default y full)
├── .env.example                # Plantilla de variables de entorno
├── nginx/
│   └── nginx.conf              # Configuración del balanceador de carga local
├── docs/
│   └── openapi/                # Contratos y esquemas OpenAPI 3.0 (RNF-API-01)
├── backend/
│   ├── alembic/                # Migraciones de base de datos relacional
│   ├── src/
│   │   ├── modules/
│   │   │   ├── content/        # Módulo 1: Cartas y Ubicaciones (Sprint 1)
│   │   │   ├── identity/       # Módulo 2: Sesiones y Cuentas (Sprint 2)
│   │   │   ├── players/        # Módulo 3: Mazos, Perfil y Elo (Sprint 2)
│   │   │   ├── game/           # Módulo 4: Matchmaking y Motor Puro (Sprint 3)
│   │   │   └── tournaments/    # Módulo 5: Torneos B2B (Sprint 4)
│   │   ├── shared/             # Kernel compartido (RFC 7807, DB, UoW, Mongo)
│   │   └── main.py             # Punto de entrada FastAPI y middlewares
│   ├── tests/
│   │   ├── architecture/       # Pruebas de fronteras hexagonales (RNF-ARQ-04)
│   │   ├── concurrency/        # Pruebas de concurrencia e invariantes (RNF-PRU-03)
│   │   ├── integration/        # Pruebas de integración E2E contra contenedores
│   │   └── unit/               # Pruebas unitarias de dominio
│   ├── Dockerfile
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── modules/
    │   │   └── content/        # Componentes y vistas de Cartas y Ubicaciones
    │   ├── shared/             # Cliente API (RFC 7807), tipos y Navbar
    │   ├── App.tsx
    │   └── main.tsx
    ├── Dockerfile
    ├── package.json
    ├── tailwind.config.js
    └── vite.config.ts
```
