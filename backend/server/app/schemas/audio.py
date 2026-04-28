from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AudioPayload(BaseModel):
    """MQTT inbound — ESP32 publishes this to farmshield/audio."""

    deviceid: str = Field(default="farmshield-node-1", alias="deviceid")
    fft_bands: list[float] = Field(..., min_length=8, max_length=8)
    db_level: float
    dominant_freq_hz: float
    ts: Optional[int] = None

    model_config = {"populate_by_name": True}


class AudioInferenceOut(BaseModel):
    """API outbound — inference result."""

    id: uuid.UUID
    time: datetime
    deviceid: str
    pest_class: str
    confidence: float
    db_level: float
    dominant_freq_hz: float
    all_scores: dict[str, float]
    alert_triggered: bool

    model_config = {"from_attributes": True, "populate_by_name": True}


class DemoTriggerRequest(BaseModel):
    """POST /api/v1/audio/demo — trigger a crafted detection."""

    pest_class: str = Field(
        default="grasshopper",
        pattern="^(grasshopper|cricket|cicada|mosquito|no_pest)$",
    )
    deviceid: str = Field(default="farmshield-node-1")


class DemoTriggerResponse(BaseModel):
    status: str
    pest_class: str
    confidence: float
    alert_triggered: bool
    mqtt_payload_published: bool
