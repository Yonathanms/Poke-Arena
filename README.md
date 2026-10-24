#  Poké-Arena – Plataforma de Cartas Coleccionables

Repositorio del proyecto del curso **CE-116: Diseño y Calidad en Productos Tecnológicos** (ITCR).  
Equipo de Desarrollo: **MAFY**.

---

##  Arquitectura del Sistema

El sistema implementa una arquitectura de **Monolito Modular con Diseño Hexagonal (Ports & Adapters)** y separación de responsabilidades:
* **Frontend:** React 18, TypeScript (modo estricto), Vite, Tailwind CSS (diseño *dark gaming* con paleta Pokémon) y Lucide Icons.
* **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic, Motor (driver async MongoDB) y Pillow.
* **Bases de Datos & Persistencia:**
  * **PostgreSQL 16 (Master & Réplica):** Modelo relacional transaccional (cartas, ubicaciones, usuarios, partidas). Separación de sesiones de escritura (Master en `:5432`) y lectura (Réplica en `:5433`).
  * **MongoDB 7.0 (`:27017`):** Proyecciones desnormalizadas de lectura ultrarrápida para catálogo y búsquedas.
  * **Almacenamiento Local de Imágenes:** Validación estricta de relación de aspecto en servidor (5:7 para cartas, 4:3 para ubicaciones) y conversión a WebP optimizado con miniaturas.
* **Infraestructura & Red:** Nginx como balanceador de carga / proxy inverso (`:80`) distribuyendo el tráfico entre múltiples instancias del backend y sirviendo la SPA.
* **Estándar de Errores:** Respuestas de error basadas en **RFC 7807 (Problem Details for HTTP APIs)** y trazabilidad con `X-Correlation-ID`.

---

##  Software y Requisitos Previos

Antes de comenzar, asegúrate de tener instalado en tu máquina:

1. **Git:** Para control de versiones ([Descargar Git](https://git-scm.com/)).
2. **Docker Desktop:** Versión moderna con soporte para Docker Compose v2 ([Descargar Docker Desktop](https://www.docker.com/products/docker-desktop/)).
   * *En Windows, asegúrate de tener WSL 2 habilitado.*
3. **Node.js:** Versión 18.x o 20.x LTS ([Descargar Node.js](https://nodejs.org/)).
   * Incluye `npm` para gestión de dependencias del frontend.
4. **Python:** Versión **3.12.x** ([Descargar Python 3.12](https://www.python.org/downloads/)).
   * Asegúrate de marcar la casilla *"Add Python to PATH"* durante la instalación en Windows.

---

##  Instalación de Dependencias

### 1. Variables de Entorno Globales
Copia el archivo de plantilla a la raíz del proyecto para crear tu archivo `.env`:

* **En Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
* **En Linux / macOS:**
  ```bash
  cp .env.example .env
  ```

---

### 2. Frontend (React + Vite + TypeScript)

1. Abre una terminal y dirígete a la carpeta `frontend/`:
   ```bash
   cd frontend
   ```
2. Instala todas las dependencias del proyecto:
   ```bash
   npm install
   ```
3. *(Opcional)* Para verificar que los tipos y el empaquetado compilen sin errores:
   ```bash
   npm run build
   ```

---

### 3. Backend (FastAPI + Python)

1. Abre una terminal y dirígete a la carpeta `backend/`:
   ```bash
   cd backend
   ```
2. Crea un entorno virtual aislado con Python 3.12:
   * **Windows:**
     ```powershell
     python -m venv .venv
     ```
   * **Linux / macOS:**
     ```bash
     python3.12 -m venv .venv
     ```
3. Activa el entorno virtual:
   * **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
     *(Si PowerShell bloquea la ejecución de scripts, ejecuta antes: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*
   * **Linux / macOS:**
     ```bash
     source .venv/bin/activate
     ```
4. Actualiza `pip` e instala el paquete backend junto con las dependencias de desarrollo (`dev`):
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

---

##  Guía de Ejecución del Proyecto

Disponemos de dos modos de trabajo según la necesidad:

###  Modo 1: Desarrollo Diario con Hot-Reload (Recomendado para Programar)
Este modo es el más cómodo para programar. Levanta únicamente los motores de base de datos en Docker y ejecuta el frontend y el backend directamente en tu máquina con recarga en caliente instantánea al editar código.

#### Paso 1: Levantar las Bases de Datos
En la raíz del proyecto:
```bash
docker compose up -d
```
*(Esto levantará `postgres-master`, `postgres-replica` y `mongo` en segundo plano).*

#### Paso 2: Iniciar el Backend
En una terminal con el entorno virtual activado (`cd backend`):
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
* API disponible en: [http://localhost:8000](http://localhost:8000)
* Documentación interactiva Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
* Healthcheck: [http://localhost:8000/health](http://localhost:8000/health)

#### Paso 3: Iniciar el Frontend
En otra terminal (`cd frontend`):
```bash
npm run dev
```
* Abre tu navegador en: [http://localhost:5173](http://localhost:5173)
* *(Nota: Las peticiones a `/api/` se redirigen automáticamente al backend en el puerto 8000).*

#### Paso 4: Apagar las Bases de Datos al Terminar
Cuando termines de trabajar:
```bash
docker compose down
```

---

###  Modo 2: Evaluación Completa en Docker (Full Stack)
Este modo levanta la infraestructura completa en contenedores de Docker (Bases de datos + 2 réplicas del Backend + Frontend en Nginx + Balanceador de Carga). Es ideal para pruebas integrales, entregas y evaluación.

#### Paso 1: Levantar todo el Clúster
En la raíz del proyecto:
```bash
docker compose --profile full up -d --build
```

#### Paso 2: Probar el Sistema en el Navegador
* **Frontend Web (Aplicación completa):** [http://localhost](http://localhost) (o [http://localhost:80](http://localhost:80))
* **Healthcheck balanceado (Nginx -> Backends):** [http://localhost/api/v1/health](http://localhost/api/v1/health)
* **API Docs (Swagger):** [http://localhost/docs](http://localhost/docs)

#### Paso 3: Monitorear Logs
Para ver los logs en tiempo real de todos los servicios:
```bash
docker compose logs -f
```
O de un servicio específico (ej. el backend):
```bash
docker compose logs -f backend-1
```

#### Paso 4: Apagar el Clúster Completo
Para detener todos los contenedores:
```bash
docker compose --profile full down
```

Si necesitas limpiar también los volúmenes de datos (reset total de bases de datos):
```bash
docker compose --profile full down -v
```

---

##  Pruebas Automatizadas y Calidad de Código

### Backend

Desde la carpeta `backend/` con el entorno virtual activo:

1. **Ejecutar Suite de Pruebas (Pytest):**
   ```bash
   pytest -v
   ```
2. **Ejecutar Linter (Ruff):**
   ```bash
   ruff check .
   ```
3. **Comprobar Tipado Estricto (Mypy):**
   ```bash
   mypy src/
   ```

*También puedes correr los tests dentro de Docker en cualquier momento:*
```bash
docker compose run --rm backend-1 pytest -v
```

### Frontend

Desde la carpeta `frontend/`:

1. **Validación de Tipos y Compilación:**
   ```bash
   npm run build
   ```

---

##  Estructura del Repositorio

```text
Poke-Arena/
├── backend/
│   ├── alembic/                # Migraciones de base de datos relacional
│   ├── src/
│   │   ├── modules/
│   │   │   └── content/        # Módulo de Cartas y Ubicaciones (Sprint 1)
│   │   │       ├── application/
│   │   │       ├── domain/
│   │   │       ├── infrastructure/
│   │   │       ├── presentation/
│   │   │       └── contracts.py
│   │   ├── shared/             # Kernel compartido (RFC 7807, DB, UoW, Mongo)
│   │   └── main.py             # Punto de entrada FastAPI y routers
│   ├── tests/                  # Pruebas unitarias, de integración y arquitectura
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── modules/
│   │   │   └── content/        # Vistas y componentes de Cartas y Ubicaciones
│   │   │       ├── components/
│   │   │       └── types/
│   │   ├── shared/             # Cliente API, tipos RFC 7807 y Navbar
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css           # Tailwind + diseño personalizado
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── nginx/
│   └── nginx.conf              # Configuración del balanceador de carga
├── docker-compose.yml          # Orquestación Docker (perfiles default y full)
├── .env.example                # Variables de entorno de referencia
└── README.md                   # Esta guía
```
