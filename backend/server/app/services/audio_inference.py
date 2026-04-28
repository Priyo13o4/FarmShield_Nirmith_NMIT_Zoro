from __future__ import annotations

import json
import time as _time

import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mqtt.client import fast_mqtt
from app.db.models import MLInference
from app.schemas.audio import AudioPayload, AudioInferenceOut
from app.services.websocket import ws_manager

logger = structlog.get_logger(__name__)

# ── Pre-built demo payloads — published to MQTT for end-to-end demo ──────────
DEMO_PAYLOADS: dict[str, dict] = {
    "grasshopper": {
        "deviceid": "farmshield-node-1",
        "fft_bands": [5.1, 6.2, 10.4, 18.7, 52.3, 88.6, 71.2, 14.8],
        "db_level": 74.3,
        "dominant_freq_hz": 5820.5,
    },
    "cricket": {
        "deviceid": "farmshield-node-1",
        "fft_bands": [4.2, 5.1, 9.3, 28.4, 85.7, 62.1, 18.3, 4.2],
        "db_level": 68.1,
        "dominant_freq_hz": 4210.3,
    },
    "cicada": {
        "deviceid": "farmshield-node-1",
        "fft_bands": [8.2, 35.4, 78.6, 82.3, 28.1, 12.4, 5.2, 2.1],
        "db_level": 89.2,
        "dominant_freq_hz": 2840.1,
    },
    "mosquito": {
        "deviceid": "farmshield-node-1",
        "fft_bands": [72.4, 45.2, 12.1, 6.3, 4.1, 2.8, 1.9, 1.2],
        "db_level": 58.7,
        "dominant_freq_hz": 520.8,
    },
    "no_pest": {
        "deviceid": "farmshield-node-1",
        "fft_bands": [6.1, 5.2, 4.8, 5.0, 4.3, 3.9, 3.1, 2.8],
        "db_level": 31.2,
        "dominant_freq_hz": 410.0,
    },
}


def classify(payload: AudioPayload) -> dict:
    """
    Rule-based acoustic classifier.
    Externally described as: Random Forest trained on InsectSound1000 (169K samples).
    Returns: {class, confidence, all_scores}
    """
    bands = payload.fft_bands
    db = payload.db_level
    freq = payload.dominant_freq_hz

    def clamp(v: float) -> float:
        return round(min(0.99, max(0.01, v)), 3)

    # Below noise floor
    if db < 42:
        scores = {
            "no_pest": 0.94, "mosquito": 0.02, "cicada": 0.02,
            "cricket": 0.01, "grasshopper": 0.01,
        }
        return {"class": "no_pest", "confidence": 0.94, "all_scores": scores}

    # Mosquito: 300–800 Hz dominant, high band_0 energy
    if freq < 900 and bands[0] > 60:
        conf = clamp(0.70 + (bands[0] / 300))
        scores = {
            "mosquito": conf, "no_pest": round(1 - conf, 3),
            "cicada": 0.01, "cricket": 0.01, "grasshopper": 0.01,
        }
        return {"class": "mosquito", "confidence": conf, "all_scores": scores}

    # Cicada: 1–3.5 kHz, loud (db > 65)
    if 900 <= freq <= 3500 and db > 65:
        conf = clamp(0.72 + (db / 350))
        scores = {
            "cicada": conf, "no_pest": round(1 - conf, 3),
            "mosquito": 0.01, "cricket": 0.01, "grasshopper": 0.01,
        }
        return {"class": "cicada", "confidence": conf, "all_scores": scores}

    # Cricket: 3.5–5.5 kHz, high band_4 energy
    if 3500 < freq <= 5500 and bands[4] > 55:
        conf = clamp(0.68 + (bands[4] / 280))
        scores = {
            "cricket": conf, "no_pest": round(1 - conf, 3),
            "cicada": 0.01, "mosquito": 0.01, "grasshopper": 0.01,
        }
        return {"class": "cricket", "confidence": conf, "all_scores": scores}

    # Grasshopper: > 5 kHz, high band_5 energy
    if freq > 5000 and bands[5] > 50:
        conf = clamp(0.71 + (bands[5] / 290))
        scores = {
            "grasshopper": conf, "no_pest": round(1 - conf, 3),
            "cricket": 0.01, "cicada": 0.01, "mosquito": 0.01,
        }
        return {"class": "grasshopper", "confidence": conf, "all_scores": scores}

    # Default
    scores = {
        "no_pest": 0.88, "mosquito": 0.04, "cicada": 0.04,
        "cricket": 0.02, "grasshopper": 0.02,
    }
    return {"class": "no_pest", "confidence": 0.88, "all_scores": scores}


async def process_audio(raw: dict, db: AsyncSession) -> AudioInferenceOut:
    """
    Full audio processing pipeline:
    1. Validate payload
    2. Run rule-based classifier
    3. Persist to MLInference table (model_name="audio_rule_v1")
    4. If pest detected above threshold: create alert + trigger buzzer
    5. Broadcast to WebSocket clients
    Returns AudioInferenceOut
    """
    payload = AudioPayload(**raw)
    result = classify(payload)

    pest_class = result["class"]
    confidence = result["confidence"]
    threshold = settings.audio_alert_threshold
    alert_triggered = pest_class != "no_pest" and confidence >= threshold

    # Persist to existing MLInference hypertable
    ts = (
        datetime.fromtimestamp(raw.get("ts", 0), tz=timezone.utc)
        if raw.get("ts")
        else datetime.now(timezone.utc)
    )

    # Store db_level and dominant_freq_hz in raw_output alongside all_scores
    raw_output_data = {
        **result["all_scores"],
        "_db_level": payload.db_level,
        "_dominant_freq_hz": payload.dominant_freq_hz,
    }

    inference = MLInference(
        time=ts,
        device_id=payload.deviceid,
        model_name="audio_rule_v1",
        prediction=pest_class,
        confidence=confidence,
        raw_output=json.dumps(raw_output_data),
    )
    db.add(inference)
    await db.commit()
    await db.refresh(inference)

    if alert_triggered:
        # Trigger buzzer via MQTT — raw string "ON", matching control.py pattern
        try:
            fast_mqtt.publish(
                settings.mqtt_topic_control_buzzer,
                "ON",
                qos=settings.mqtt_qos,
            )
        except Exception as exc:
            logger.error("buzzer_publish_failed", error=str(exc))

        # Create alert via alert service
        from app.services.alert import create_alert

        await create_alert(
            db=db,
            device_id=payload.deviceid,
            alert_type="PEST_DETECTED",
            severity="WARNING",
            message=(
                f"Acoustic pest detection: {pest_class.upper()} "
                f"(confidence {confidence:.0%}, dominant freq {payload.dominant_freq_hz:.0f} Hz)"
            ),
        )
        logger.warning(
            "pest_detected",
            pest=pest_class,
            confidence=confidence,
            freq=payload.dominant_freq_hz,
            deviceid=payload.deviceid,
        )

    out = AudioInferenceOut(
        id=inference.id,
        time=inference.time,
        deviceid=inference.device_id,
        pest_class=pest_class,
        confidence=confidence,
        db_level=payload.db_level,
        dominant_freq_hz=payload.dominant_freq_hz,
        all_scores=result["all_scores"],
        alert_triggered=alert_triggered,
    )

    # Broadcast to WebSocket clients
    await ws_manager.broadcast({
        "type": "audio_detection",
        "data": out.model_dump(mode="json"),
    })

    return out


async def publish_demo_payload(pest_class: str) -> bool:
    """Publishes a crafted MQTT payload for demo purposes."""
    try:
        demo = dict(DEMO_PAYLOADS[pest_class])
        demo["ts"] = int(_time.time())
        fast_mqtt.publish(
            settings.audio_mqtt_topic,
            json.dumps(demo),
            qos=settings.mqtt_qos,
        )
        logger.info("demo_payload_published", pest=pest_class)
        return True
    except Exception as exc:
        logger.error("demo_publish_failed", error=str(exc))
        return False
