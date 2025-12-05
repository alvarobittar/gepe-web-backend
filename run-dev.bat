#!/bin/sh
set -e
echo "Starting uvicorn on port ${PORT:-8000}..."
echo "Python version: $(python --version)"
exec python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level debug

