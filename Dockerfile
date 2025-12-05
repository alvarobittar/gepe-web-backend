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

# Hacer ejecutable el script de inicio
RUN chmod +x start.sh

# Exponer el puerto (Railway lo configurará automáticamente)
EXPOSE 8000

# Comando de inicio usando el script
# Railway inyecta PORT automáticamente como variable de entorno
ENTRYPOINT ["./start.sh"]

