#!/bin/sh
# server/entrypoint.sh
# Runs Alembic migrations then starts Uvicorn.
# Reload mode is controlled by the FASTAPI_RELOAD env var.

set -e

# Ensure app module is importable by Alembic
export PYTHONPATH=/app

# Chat dependencies are now baked into the Docker image via Dockerfile

# Always run migrations first
echo "Running Alembic migrations..."
alembic upgrade head

# Start server — reload mode controlled by env
if [ "$FASTAPI_RELOAD" = "true" ]; then
    echo "Starting Uvicorn with --reload (dev mode)"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "Starting Uvicorn (production mode)"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
