#!/bin/sh
set -e
echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 120 --log-level info

