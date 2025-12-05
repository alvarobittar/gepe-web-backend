#!/bin/sh
set -e
echo "Starting uvicorn on port ${PORT:-8000}..."
exec python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info --timeout-keep-alive 300 --timeout-graceful-shutdown 30

