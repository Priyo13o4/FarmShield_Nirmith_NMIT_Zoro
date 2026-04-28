#!/bin/sh
# server/entrypoint.sh
# Runs Alembic migrations then starts Uvicorn.
# Reload mode is controlled by the FASTAPI_RELOAD env var.

set -e

# Ensure app module is importable by Alembic
export PYTHONPATH=/app

# Install chat dependencies if feature is enabled
# This keeps the base image lean — LangChain/FAISS only pulled when needed
# Note: pip install -e ".[chat]" fails when setuptools sees both app/ and alembic/
# as top-level packages (flat-layout discovery error). Install packages directly instead.
if [ "$CHAT_ENABLED" = "true" ]; then
    echo "CHAT_ENABLED=true: installing chat dependencies..."
    pip install --no-cache-dir \
        "langchain>=0.3.0" \
        "langchain-google-genai>=2.0.0" \
        "langchain-community>=0.3.0" \
        "faiss-cpu>=1.9.0" \
        "psycopg2-binary>=2.9.0"
fi

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
