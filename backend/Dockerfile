FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas para compilar extensiones C si hiciera falta
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar configuración de dependencias
COPY pyproject.toml .

# Instalar pip y dependencias del backend
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copiar el código fuente y las migraciones
COPY . .

# Crear carpeta de subidas
RUN mkdir -p /app/uploads

EXPOSE 8000

# Ejecución bajo Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
