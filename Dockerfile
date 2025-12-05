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
RUN chmod +x start.sh run-dev.bat entrypoint.sh

# Copiar run-dev.bat al PATH para que Railway lo encuentre cuando lo ejecute como comando
# Railway tiene "run-dev.bat" guardado como Start Command en su configuración
RUN cp run-dev.bat /usr/local/bin/run-dev.bat && chmod +x /usr/local/bin/run-dev.bat

# Exponer el puerto (Railway lo configurará automáticamente)
EXPOSE 8000

# Comando de inicio - usar entrypoint.sh que mantiene el proceso vivo
CMD ["./entrypoint.sh"]

