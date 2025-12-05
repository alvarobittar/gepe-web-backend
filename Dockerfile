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

# Hacer ejecutables los scripts de inicio
# run-dev.bat es requerido porque Railway tiene ese comando guardado en su config
RUN chmod +x start.sh run-dev.bat

# Exponer el puerto (Railway lo configurará automáticamente)
EXPOSE 8000

# Comando de inicio
ENTRYPOINT ["./start.sh"]

