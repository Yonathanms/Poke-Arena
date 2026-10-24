# Poké-Arena – Plataforma de Cartas Coleccionables

Repositorio del proyecto correspondiente al curso **CE-116: Diseño y Calidad en Productos Tecnológicos** (Instituto Tecnológico de Costa Rica).  
Equipo de Desarrollo: **MAFY**.

---

## Inicio Rápido Centralizado (`manage.py`)

El repositorio dispone de una interfaz de línea de comandos centralizada en Python (`manage.py`) para estandarizar las tareas de instalación, ejecución y pruebas en entornos Windows, Linux y macOS:

```bash
# 1. Instalación automatizada de dependencias (Backend y Frontend)
python manage.py install-deps

# 2. Despliegue del sistema completo en Docker
python manage.py start-full

# 3. Acceso a la aplicación en el navegador
# http://localhost
```

---

## Panel de Comandos de `manage.py`

| Comando | Descripción Técnica | Caso de Uso Recomendado |
| :--- | :--- | :--- |
| **`python manage.py install-deps`** | Genera el archivo `.env` a partir de la plantilla, crea el entorno virtual `.venv` en `backend/`, instala las dependencias de Python e invoca `npm install` en `frontend/`. | Se recomienda ejecutar al clonar el repositorio o al actualizar paquetes del proyecto. *(Alias: `install`)* |
| **`python manage.py start-dbs`** | Inicializa exclusivamente los contenedores de bases de datos en Docker (PostgreSQL Master en `:5432`, PostgreSQL Réplica en `:5433` y MongoDB en `:27017`). | Se recomienda para el desarrollo diario con recarga en caliente en la máquina local. *(Alias: `dbs`)* |
| **`python manage.py start-full`** | Construye y ejecuta el clúster completo en Docker (motores de base de datos, dos instancias del Backend en FastAPI, SPA de Frontend compilada y balanceador de carga Nginx en el puerto `:80`). | Se recomienda para pruebas de integración, evaluación de arquitectura y demostraciones. *(Alias: `up`)* |
| **`python manage.py stop`** | Detiene todos los contenedores en ejecución **conservando los volúmenes de datos persistentes** en PostgreSQL y MongoDB. | Se recomienda para pausar la sesión de trabajo sin perder la información almacenada en las bases de datos. *(Alias: `down`)* |
| **`python manage.py stop-clean`** | Detiene los contenedores y **elimina los volúmenes persistentes** asociados al clúster. | Se recomienda para restablecer completamente las bases de datos a su estado inicial. *(Alias: `clean`)* |
| **`python manage.py status`** | Consulta y presenta el estado de ejecución, puertos expuestos y comprobaciones de salud de los contenedores. | Se recomienda para verificar la disponibilidad de los servicios del clúster. |
| **`python manage.py logs`** | Transmite la salida de registros (*logs*) de los contenedores en tiempo real. Admite filtrar por servicio específico (ejemplo: `python manage.py logs backend-1`). | Se recomienda para tareas de diagnóstico y depuración de red o persistencia. |
| **`python manage.py test`** | Ejecuta la suite de pruebas unitarias y de arquitectura modular mediante `pytest`. | Se recomienda ejecutar antes de crear confirmaciones (*commits*) o solicitudes de extracción (*pull requests*). *(Alias: `run-tests`)* |
| **`python manage.py lint`** | Ejecuta el analizador de código `Ruff` y la comprobación de tipado estricto con `Mypy`. | Se recomienda para garantizar el cumplimiento de los estándares de codificación del proyecto. *(Alias: `run-lint`)* |
| **`python manage.py smoke-test`** | Ejecuta la prueba de verificación de signos vitales (comprobación de conectividad a bases de datos, documentación interactiva y ciclo de persistencia de cartas). | Se recomienda para certificar la estabilidad de la infraestructura tras un nuevo despliegue. *(Alias: `smoke`)* |

---

## Flujo de Trabajo Recomendado para Desarrollo Diario

Para optimizar el ciclo de desarrollo del Frontend y del Backend sin incurrir en los tiempos de reconstrucción de imágenes Docker, se recomienda estructurar la sesión de trabajo en tres terminales independientes:

### Terminal 1: Bases de Datos en Docker
Este comando inicializa los motores de persistencia en segundo plano y deja la terminal disponible:
```bash
python manage.py start-dbs
```

### Terminal 2: Servidor de Aplicación (Backend)
Este comando ejecuta la API en modo de recarga automática (*hot-reload*) en el puerto 8000:
```bash
cd backend
.venv\Scripts\Activate.ps1   # En Windows PowerShell (o: source .venv/bin/activate en Linux/macOS)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
* La documentación interactiva queda accesible en: `http://localhost:8000/docs`
* La verificación de salud queda disponible en: `http://localhost:8000/api/v1/health`

### Terminal 3: Servidor de Desarrollo (Frontend)
Este comando ejecuta el servidor de desarrollo de Vite con recarga instantánea ante cambios en el código fuente:
```bash
cd frontend
npm run dev
```
* La aplicación queda accesible en: `http://localhost:5173`
* Las solicitudes dirigidas a `/api/` son redirigidas automáticamente mediante proxy al Backend en el puerto 8000.
* Para detener el servidor de desarrollo al finalizar la sesión, se utiliza la combinación de teclas `Ctrl + C`.

---

## Criterios de Selección entre Comandos de Despliegue y Apagado

### Comparación entre `start-dbs` y `start-full`
* **`start-dbs`:** Debe utilizarse durante la fase activa de programación. Levanta únicamente los servicios de base de datos requeridos, permitiendo que tanto el código de Python como los componentes de TypeScript se ejecuten directamente sobre la máquina anfitriona con retroalimentación inmediata.
* **`start-full`:** Debe utilizarse para validar la integración de arquitectura distribuida. Encapsula todos los componentes detrás del balanceador de carga Nginx en el puerto 80, replicando fielmente las condiciones de un entorno productivo.

### Comparación entre `stop` y `stop-clean`
* **`stop`:** Detiene los contenedores preservando la integridad de los datos almacenados en los volúmenes de PostgreSQL y MongoDB.
* **`stop-clean`:** Detiene los contenedores y remueve los volúmenes de almacenamiento (`docker compose down -v`). Este procedimiento se reserva exclusivamente para limpiezas de entorno y reinicio de esquemas de datos.

---

## Arquitectura del Sistema

El sistema implementa una arquitectura de **Monolito Modular con Diseño Hexagonal (Ports & Adapters)**:
* **Frontend:** React 18, TypeScript (modo estricto `strict: true`), Vite, Tailwind CSS y Lucide Icons.
* **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (modo asíncrono con `asyncpg`), Alembic, Motor (driver asíncrono para MongoDB) y Pillow.
* **Persistencia Políglota (`RNF-ALM-01`):**
  * **PostgreSQL 16 (Master y Réplica):** Modelo relacional transaccional (ACID). Aplica separación de sesiones de escritura (Master en `:5432`) y sesiones de lectura (Réplica en `:5433`, `RNF-DIS-02`).
  * **MongoDB 7.0 (`:27017`):** Proyecciones desnormalizadas para consultas de catálogo de baja latencia sin operaciones de combinación (*joins*, `US 2.1.2`).
  * **Almacenamiento Local de Imágenes:** Validación estricta de proporciones en servidor (5:7 para cartas y 4:3 para ubicaciones) con generación de miniaturas y optimización WebP.
* **Infraestructura y Red:** Nginx operando como balanceador de carga inverso (`:80`) para distribuir tráfico entre múltiples réplicas del Backend (`RNF-REN-03`).
* **Estándar de Errores:** Respuestas estandarizadas bajo el formato **RFC 7807 (Problem Details)** con trazabilidad obligatoria mediante cabecera `X-Correlation-ID` (`RNF-OBS-01`).

---

## Requisitos Previos de Software

Para la correcta ejecución del entorno, se requiere contar con las siguientes herramientas instaladas:
1. **Git:** Sistema de control de versiones ([Descargar Git](https://git-scm.com/)).
2. **Docker Desktop:** Con soporte para Docker Compose v2 ([Descargar Docker Desktop](https://www.docker.com/products/docker-desktop/)).
3. **Node.js:** Versión 18.x o 20.x LTS con gestor de paquetes `npm` ([Descargar Node.js](https://nodejs.org/)).
4. **Python:** Versión **3.12.x** con `pip` habilitado en las variables de entorno de la máquina ([Descargar Python 3.12](https://www.python.org/downloads/)).

---

## Pruebas Automatizadas y Aseguramiento de Calidad

Los estándares de verificación de código se ejecutan mediante las siguientes instrucciones:

```bash
# 1. Pruebas unitarias de dominio y arquitectura modular
python manage.py test

# 2. Análisis estático de estilo (Ruff) y tipado estricto (Mypy)
python manage.py lint

# 3. Verificación de signos vitales de extremo a extremo
python manage.py smoke-test
```

---

## Estructura del Repositorio

```text
Poke-Arena/
├── manage.py                   # Interfaz de comandos centralizada para gestión del proyecto
├── docker-compose.yml          # Definición de servicios y perfiles de Docker Compose
├── .env.example                # Plantilla de variables de entorno del sistema
├── nginx/
│   └── nginx.conf              # Configuración del balanceador de carga local
├── docs/
│   └── openapi/                # Contratos y esquemas OpenAPI 3.0 (RNF-API-01)
├── backend/
│   ├── alembic/                # Versionamiento de migraciones relacionales
│   ├── src/
│   │   ├── modules/
│   │   │   ├── content/        # Módulo 1: Cartas y Ubicaciones (Sprint 1)
│   │   │   ├── identity/       # Módulo 2: Cuentas y Sesiones (Sprint 2)
│   │   │   ├── players/        # Módulo 3: Mazos, Perfil y Clasificación (Sprint 2)
│   │   │   ├── game/           # Módulo 4: Partidas y Motor Puro Determinista (Sprint 3)
│   │   │   └── tournaments/    # Módulo 5: Socios B2B y Torneos (Sprint 4)
│   │   ├── shared/             # Kernel compartido (RFC 7807, conexiones, UoW)
│   │   └── main.py             # Punto de entrada de FastAPI y registro de rutas
│   ├── tests/
│   │   ├── architecture/       # Pruebas de cumplimiento de fronteras modulares (RNF-ARQ-04)
│   │   ├── concurrency/        # Pruebas de concurrencia e invariantes (RNF-PRU-03)
│   │   ├── integration/        # Pruebas de integración contra base de datos
│   │   └── unit/               # Pruebas unitarias de reglas de dominio
│   ├── Dockerfile
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── modules/
    │   │   └── content/        # Componentes y tipos de Cartas y Ubicaciones
    │   ├── shared/             # Cliente API tipado, manejo RFC 7807 y barra de navegación
    │   ├── App.tsx
    │   └── main.tsx
    ├── Dockerfile
    ├── package.json
    ├── tailwind.config.js
    └── vite.config.ts
```
