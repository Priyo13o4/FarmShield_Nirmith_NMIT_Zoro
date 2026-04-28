"""
FarmShield Backend — Test Configuration & Fixtures.

All tests are async. Tests never connect to a real DB or MQTT broker.
Provides:
  - async_client: httpx.AsyncClient with AUTH_ENABLED=false
  - auth_client: httpx.AsyncClient with AUTH_ENABLED=true
  - mock_db_session: mocked AsyncSession
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Override env vars BEFORE importing app modules
os.environ.update({
    "MQTT_USERNAME": "test",
    "MQTT_PASSWORD": "test",
    "MQTT_BROKER_HOST": "localhost",
    "DB_HOST": "localhost",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "DB_NAME": "test",
    "AUTH_ENABLED": "false",
    "ML_ENABLED": "false",
    "API_KEY": "test-api-key",
    "LOG_LEVEL": "DEBUG",
    "LOG_JSON": "false",
})


@pytest.fixture
def mock_db_session():
    """A mocked AsyncSession for service-level tests."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_mqtt_client():
    """A mocked MQTT client."""
    client = MagicMock()
    client.publish = MagicMock()
    client.client = MagicMock()
    client.client.is_connected = True
    return client


@pytest.fixture
async def async_client():
    """
    httpx.AsyncClient with AUTH_ENABLED=false.

    Patches out the lifespan to skip DB/MQTT/ML startup,
    and overrides the DB dependency.
    """
    from contextlib import asynccontextmanager

    from app.dependencies import get_db
    from app.main import app

    # Patch lifespan to be a no-op
    @asynccontextmanager
    async def mock_lifespan(app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = mock_lifespan

    # Override get_db with a mock session
    async def mock_get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Restore
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client():
    """
    httpx.AsyncClient with AUTH_ENABLED=true for auth testing.
    """
    from contextlib import asynccontextmanager

    from app.dependencies import get_db
    from app.main import app

    @asynccontextmanager
    async def mock_lifespan(app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = mock_lifespan

    async def mock_get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = mock_get_db

    # Temporarily enable auth
    from app.config import settings

    original_auth = settings.auth_enabled
    settings.auth_enabled = True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    settings.auth_enabled = original_auth
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()
