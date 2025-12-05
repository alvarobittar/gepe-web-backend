FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar el caché de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Railway inyecta PORT como variable de entorno
ENV PORT=8080

# Comando de inicio - shell form para que interprete la variable $PORT
CMD python -m uvicorn src.main:app --host 0.0.0.0 --port $PORT

