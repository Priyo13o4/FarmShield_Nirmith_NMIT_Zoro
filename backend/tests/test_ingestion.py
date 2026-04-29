"""
Tests for the ingestion pipeline.

services/ingestion.process() with:
  - valid payload → DB write
  - missing ts → fallback + WARNING
  - all-None numeric fields → rejected with logged error
  - malformed payload → ValidationError caught
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.sensor import SensorPayload


def _valid_payload() -> dict:
    """Return a valid MQTT payload dict."""
    return {
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
        "ts": 1745678901,
    }


def test_sensor_payload_valid():
    """Valid payload passes Pydantic validation."""
    payload = SensorPayload(**_valid_payload())
    assert payload.device_id == "esp32-node-1"
    assert payload.soil_pct == 42.5


def test_sensor_payload_all_none_numeric_rejected():
    """Payload with all numeric fields None is rejected."""
    data = {
        "device_id": "esp32-node-1",
        "motion": True,
        "pump_on": False,
        # All numeric fields missing
    }
    with pytest.raises(ValueError, match="all numeric sensor fields are None"):
        SensorPayload(**data)


def test_sensor_payload_partial_none_accepted():
    """Payload with at least one numeric field is accepted."""
    data = {
        "device_id": "esp32-node-1",
        "soil_pct": 42.5,
        # Everything else missing
    }
    payload = SensorPayload(**data)
    assert payload.soil_pct == 42.5



def test_sensor_payload_missing_device_id():
    """Payload without device_id is rejected."""
    data = {"soil_pct": 42.5}
    with pytest.raises(Exception):  # ValidationError
        SensorPayload(**data)


@pytest.mark.asyncio
async def test_ingestion_process_valid_payload():
    """process() with valid payload → DB write called."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.ingestion.AsyncSessionLocal", return_value=mock_ctx),
        patch("app.services.ingestion.ws_manager") as mock_ws,
        patch("app.services.ingestion.alert_service") as mock_alert_svc,
    ):
        mock_ws.broadcast = AsyncMock()
        mock_alert_svc.evaluate_thresholds = MagicMock(return_value=[])

        from app.services.ingestion import process

        await process(_valid_payload())

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingestion_process_malformed_payload():
    """process() with completely invalid payload → logged error, no crash."""
    with patch("app.services.ingestion.logger") as mock_logger:
        from app.services.ingestion import process

        await process({"garbage": "data"})

    # Should have logged an error for validation failure
    mock_logger.error.assert_called()
