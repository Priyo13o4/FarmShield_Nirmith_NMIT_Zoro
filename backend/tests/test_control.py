"""
Tests for control endpoints.

POST /api/v1/control/pump
POST /api/v1/control/mode
POST /api/v1/control/buzzer
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_pump_on(async_client):
    """Valid pump ON → 200 + correct response."""
    mock_result = {"command": "pump", "state": "ON", "published": True, "ts": 1745678901}
    with patch("app.services.control.send_pump_command", new_callable=AsyncMock, return_value=mock_result):
        response = await async_client.post("/api/v1/control/pump", json={"state": "ON"})
    assert response.status_code == 200
    assert response.json()["command"] == "pump"
    assert response.json()["state"] == "ON"


@pytest.mark.asyncio
async def test_pump_off(async_client):
    """Valid pump OFF → 200."""
    mock_result = {"command": "pump", "state": "OFF", "published": True, "ts": 1745678901}
    with patch("app.services.control.send_pump_command", new_callable=AsyncMock, return_value=mock_result):
        response = await async_client.post("/api/v1/control/pump", json={"state": "OFF"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pump_invalid_state(async_client):
    """Invalid pump state → 422."""
    response = await async_client.post("/api/v1/control/pump", json={"state": "BOOM"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_mode_auto(async_client):
    """Mode AUTO → 200."""
    mock_result = {"command": "mode", "state": "AUTO", "published": True, "ts": 1745678901}
    with patch("app.services.control.send_mode_command", new_callable=AsyncMock, return_value=mock_result):
        response = await async_client.post("/api/v1/control/mode", json={"state": "AUTO"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_mode_manual(async_client):
    """Mode MANUAL → 200."""
    mock_result = {"command": "mode", "state": "MANUAL", "published": True, "ts": 1745678901}
    with patch("app.services.control.send_mode_command", new_callable=AsyncMock, return_value=mock_result):
        response = await async_client.post("/api/v1/control/mode", json={"state": "MANUAL"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_buzzer_off(async_client):
    """Buzzer OFF → 200."""
    mock_result = {"command": "buzzer", "state": "OFF", "published": True, "ts": 1745678901}
    with patch("app.services.control.send_buzzer_command", new_callable=AsyncMock, return_value=mock_result):
        response = await async_client.post("/api/v1/control/buzzer", json={"state": "OFF"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_buzzer_on_rejected(async_client):
    """Buzzer ON → 422 (only OFF is supported)."""
    response = await async_client.post("/api/v1/control/buzzer", json={"state": "ON"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_required_when_enabled(auth_client):
    """Control endpoint with AUTH_ENABLED=true and no key → 401."""
    response = await auth_client.post("/api/v1/control/pump", json={"state": "ON"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_passes_with_valid_key(auth_client):
    """Control endpoint with correct API key → passes auth."""
    mock_result = {"command": "pump", "state": "ON", "published": True, "ts": 1745678901}
    with patch("app.services.control.send_pump_command", new_callable=AsyncMock, return_value=mock_result):
        response = await auth_client.post(
            "/api/v1/control/pump",
            json={"state": "ON"},
            headers={"Authorization": "Bearer test-api-key"},
        )
    assert response.status_code == 200
