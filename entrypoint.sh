#!/bin/sh
set -e

echo "🚀 Starting backend server..."
echo "Port: ${PORT:-8000}"
echo "Python: $(python --version)"

# Ejecutar uvicorn en foreground (no background)
# exec reemplaza el proceso del shell con uvicorn
exec python -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --log-level info \
    --timeout-keep-alive 300 \
    --timeout-graceful-shutdown 30

