"""
Tests for sensor endpoints.

GET /api/v1/sensors/latest
GET /api/v1/sensors/history
GET /api/v1/sensors/export
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import SensorReading


def _make_reading(**overrides) -> SensorReading:
    """Factory for a SensorReading ORM instance."""
    defaults = {
        "time": datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc),
        "device_id": "esp32-node-1",
        "soil_pct": 42.5,

        "tds_ppm": 410.0,
        "temp_c": 29.1,
        "humidity_pct": 58.0,
        "rain_raw": 3200,
        "motion": False,
        "npk_n": 45,
        "npk_p": 30,
        "npk_k": 60,
        "leaf_r": 80,
        "leaf_g": 140,
        "leaf_b": 60,
        "pump_on": False,
    }
    defaults.update(overrides)
    return SensorReading(**defaults)


@pytest.mark.asyncio
async def test_sensors_latest_returns_reading(async_client):
    """GET /sensors/latest with data → 200."""
    reading = _make_reading()
    with patch("app.services.sensor.get_latest", new_callable=AsyncMock, return_value=reading):
        response = await async_client.get("/api/v1/sensors/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "esp32-node-1"
    assert data["soil_pct"] == 42.5


@pytest.mark.asyncio
async def test_sensors_latest_no_data_returns_404(async_client):
    """GET /sensors/latest with no data → 404."""
    with patch("app.services.sensor.get_latest", new_callable=AsyncMock, return_value=None):
        response = await async_client.get("/api/v1/sensors/latest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sensors_history_pagination(async_client):
    """GET /sensors/history pagination → correct count."""
    readings = [_make_reading() for _ in range(3)]
    with patch("app.services.sensor.get_history", new_callable=AsyncMock, return_value=(readings, 10)):
        response = await async_client.get("/api/v1/sensors/history?hours=24&limit=3&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 10
    assert len(data["readings"]) == 3


@pytest.mark.asyncio
async def test_sensors_export_csv(async_client):
    """GET /sensors/export → text/csv content type."""
    csv_data = "time,device_id,soil_pct\n2026-04-26T12:00:00,esp32-node-1,42.5\n"
    with patch("app.services.sensor.export_csv_data", new_callable=AsyncMock, return_value=csv_data):
        response = await async_client.get("/api/v1/sensors/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Content-Disposition" in response.headers
